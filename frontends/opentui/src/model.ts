export type Item = {
  id: string;
  kind: string;
  text: string;
  status: string;
  detail: string;
};
export const palette = {
  bg: "#14191f",
  panel: "#1d242d",
  ink: "#e0e6ec",
  muted: "#a2b0bf",
  line: "#394654",
  green: "#8ed5b7",
  amber: "#e8c16f",
  red: "#f3a3ae",
};
export const monochrome = process.env.NO_COLOR !== undefined;
if (monochrome) {
  palette.green = palette.ink;
  palette.amber = palette.ink;
  palette.red = palette.ink;
}
export const safe = (text: string) =>
  text.replace(/[\x00-\x08\x0b-\x1f\x7f-\x9f]/g, "").replaceAll("\t", "    ");
export const color = (status: string) =>
  status === "failed"
    ? palette.red
    : ["succeeded", "completed"].includes(status)
      ? palette.green
      : ["waiting", "running"].includes(status)
        ? palette.amber
        : palette.muted;
export const icon = (status: string) =>
  status === "failed"
    ? "×"
    : status === "succeeded"
      ? "✓"
      : ["waiting", "running"].includes(status)
        ? "·"
        : "−";
export function wrap(text: string, width: number): string[] {
  if (width < 1) return [];
  const lines: string[] = [];
  for (const source of safe(text).split("\n")) {
    let line = "",
      size = 0;
    for (const c of source) {
      const w = Bun.stringWidth(c);
      if (size + w > width && line) {
        const space = line.lastIndexOf(" ");
        if (space >= Math.floor(width / 3)) {
          lines.push(line.slice(0, space + 1));
          line = line.slice(space + 1);
          size = Bun.stringWidth(line);
        } else {
          lines.push(line);
          line = "";
          size = 0;
        }
      }
      line += c;
      size += w;
    }
    lines.push(line);
  }
  return lines;
}
export function itemLines(
  item: Item,
  width: number,
  selected: boolean,
): [string, string][] {
  if (item.kind === "tool")
    return [
      [
        `${selected ? "›" : " "} ${icon(item.status)}  ${item.text}`,
        color(item.status),
      ],
    ];
  if (["user", "assistant"].includes(item.kind))
    return [
      [
        item.kind === "user" ? "you" : "amplifier",
        item.kind === "user" ? palette.muted : palette.green,
      ],
      ...wrap(item.text, width).map(
        (s) => [s, palette.ink] as [string, string],
      ),
      ["", palette.ink],
    ];
  return wrap(item.text, width).map((s) => [s, color(item.status)]);
}
