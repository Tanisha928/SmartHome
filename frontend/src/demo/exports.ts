import type { Alert } from "../features/alerts/types";

/** A self-contained, valid PDF using the standard Helvetica font. No external service. */
export function alertsPdf(alerts: Alert[]): string {
  const escape = (text: string) => text.replace(/[^\x20-\x7e]/g, " ").replace(/[\\()]/g, "\\$&");
  const rows = alerts.map(a => `#${a.alert_id} ${a.sound_type} | ${a.severity} | ${a.state} | ${a.created_at ?? ""}`);
  const pages = Array.from({ length: Math.max(1, Math.ceil(rows.length / 40)) }, (_, index) => rows.slice(index * 40, index * 40 + 40));
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    `<< /Type /Pages /Kids [${pages.map((_, index) => `${4 + index * 2} 0 R`).join(" ")}] /Count ${pages.length} >>`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  pages.forEach((page, index) => {
    const lines = [`Smart Home - Alert report (page ${index + 1} of ${pages.length})`, "", ...page];
    const content = `BT /F1 11 Tf 45 790 Td 17 TL ${lines.map((line, row) => `${row ? "T* " : ""}(${escape(line)}) Tj`).join("\n")} ET`;
    objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + index * 2} 0 R >>`, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
  });
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  objects.forEach((object, index) => { offsets.push(pdf.length); pdf += `${index + 1} 0 obj\n${object}\nendobj\n`; });
  const xref = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, "0")} 00000 n \n`).join("")}trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return pdf;
}
