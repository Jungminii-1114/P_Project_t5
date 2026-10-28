"""Independent index and evidence rendering over the same table registry."""

from html import escape

from langchain_core.documents import Document


def header_records(table, rows=None):
    rows = range(table.header_rows, table.n_rows) if rows is None else rows
    lines = []
    for row in rows:
        label = " / ".join(table.row_label(row)) or f"row {row+1}"
        for col in range(table.stub_cols, table.n_cols):
            cell = table.cell_at(row, col)
            if cell is None or not cell.text:
                continue
            path = "/".join(table.header_path(col)) or f"column {col+1}"
            lines.append((row, f"[{label}] {path} = {cell.text}"))
    return lines


def html_full(table, rows=None):
    selected = list(range(table.n_rows)) if rows is None else sorted(
        set(range(table.header_rows)) | set(rows))
    lines = ["<table>"]
    for offset, row in enumerate(selected):
        line = ["<tr>"]
        for col in range(table.n_cols):
            cell = table.cell_at(row, col)
            if cell is None:
                line.append("<td></td>")
                continue
            if col != cell.col:
                continue
            # Repeat a vertically merged label at the first row of each shard.
            if row != cell.row and offset and selected[offset-1] >= cell.row:
                continue
            span = sum(cell.row <= r < cell.row+cell.rowspan for r in selected[offset:])
            tag = "th" if cell.is_header else "td"
            attrs = (f' rowspan="{span}"' if span > 1 else "")
            attrs += f' colspan="{cell.colspan}"' if cell.colspan > 1 else ""
            line.append(f"<{tag}{attrs}>{escape(cell.text)}</{tag}>")
        lines.append("".join(line) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def baseline1(table, rows=None):
    from .pdf import rows_to_markdown
    selected = list(range(table.n_rows)) if rows is None else sorted(
        set(range(table.header_rows)) | set(rows))
    grid = [[(table.cell_at(r, c).text if table.cell_at(r, c) else "")
             for c in range(table.n_cols)] for r in selected]
    return rows_to_markdown(grid)


def split_records(table, max_chars):
    """Only split between complete facts; each fact retains its full path."""
    groups, group, size = [], [], 0
    for row, line in header_records(table):
        if group and size + len(line) + 1 > max_chars:
            groups.append(group)
            group, size = [], 0
        group.append((row, line))
        size += len(line) + 1
    if group:
        groups.append(group)
    return groups


def render_chunks(raw_docs, chunks, contextual, registry, config):
    from .context import build_contextual_chunks, doc_title

    by_id = {d.metadata["table_id"]: d for d in raw_docs if "table_id" in d.metadata}
    old_groups = {}
    for chunk in contextual:
        old_groups.setdefault(chunk.metadata.get("table_id"), []).append(chunk)
    full = {key: html_full(table) for key, table in registry.items()
            if table.confidence == "confident" and len(html_full(table)) <= config.table_full_max_chars}
    if config.index_render == "baseline1":
        # Index bytes are unchanged for V0/V2, enabling embedding-cache reuse.
        out = []
        for old in contextual:
            table = registry.get(old.metadata.get("table_id"))
            metadata = dict(old.metadata)
            if table and table.confidence == "confident" and config.llm_render != "baseline1":
                peers = old_groups[table.table_id]
                part, count = metadata["part"], len(peers)
                body = list(range(table.header_rows, table.n_rows))
                rows = body[len(body)*part//count:len(body)*(part+1)//count]
                text = (html_full(table, rows) if config.llm_render == "html_full" else
                        "\n".join(line for _, line in header_records(table, rows)))
                metadata["raw"] = config.chunk_prefix_template.format(**metadata) + text
            out.append(Document(page_content=old.page_content, metadata=metadata))
        return chunks, out, full

    new_chunks, new_context, seen = [], [], set()
    for old in contextual:
        key = old.metadata.get("table_id")
        table = registry.get(key)
        if table is None or table.confidence != "confident":
            meta = {**old.metadata, "chunk_id": len(new_chunks)}
            new_chunks.append(Document(page_content=old.metadata["raw"], metadata={
                k: v for k, v in meta.items() if k not in {"raw", "title"}}))
            new_context.append(Document(page_content=old.page_content, metadata=meta))
            continue
        if key in seen:
            continue
        seen.add(key)
        for part, group in enumerate(split_records(table, config.table_max_chars)):
            rows = sorted({row for row, _ in group})
            index = "\n".join(line for _, line in group)
            evidence = index if config.llm_render == "header_records" else (
                html_full(table, rows) if config.llm_render == "html_full" else baseline1(table, rows))
            meta = {**by_id[key].metadata, "part": part, "chunk_id": len(new_chunks)}
            prefix = config.chunk_prefix_template.format(**meta)
            title = doc_title(meta["source"], config)
            header = config.context_header_template.format(title=title, page=meta["page"],
                kind_label=config.kind_labels["table"], source=meta["source"], kind="table")
            raw = prefix + evidence
            new_chunks.append(Document(page_content=prefix + index, metadata=meta))
            new_context.append(Document(page_content=header + config.raw_marker + prefix + index,
                metadata={**meta, "raw": raw, "title": title}))
    return new_chunks, new_context, full


def chroma_metadata(metadata):
    """Chroma copies retain only scalar metadata; the IR remains external."""
    return {key: value for key, value in metadata.items()
            if isinstance(value, (str, int, float, bool))}
