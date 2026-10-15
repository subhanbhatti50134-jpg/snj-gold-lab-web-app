export function waLink(phone: string, text: string): string | null {
  let digits = phone.replace(/\D/g, "");
  if (!digits) return null;
  if (digits.startsWith("0")) digits = "92" + digits.slice(1);
  else if (digits.length === 10 && digits.startsWith("3"))
    digits = "92" + digits;
  if (digits.length < 10) return null;
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`;
}

export function duesReminder(
  party: string,
  shop: string,
  amount: string
): string {
  return (
    `Assalam-o-Alaikum ${party}, ${shop} par aapka ${amount} ka ` +
    `outstanding baqaya hai. Baraye meharbani jald ada farmayein. ` +
    `Shukriya — ${shop}.`
  );
}

export function openWhatsApp(phone: string, message: string): void {
  const link = waLink(phone, message);
  if (link) window.open(link, "_blank", "noopener,noreferrer");
}
