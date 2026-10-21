const units = [
	["day", 86_400_000],
	["hour", 3_600_000],
	["minute", 60_000],
] as const;

// "20 minutes", "3 hours", "2 days"; the caller adds "ago".
export function age(iso: string, now = Date.now()): string {
	const ms = Math.max(0, now - Date.parse(iso));
	for (const [unit, size] of units) {
		if (ms >= size) {
			return new Intl.NumberFormat("en", {
				style: "unit",
				unit,
				unitDisplay: "long",
			}).format(Math.floor(ms / size));
		}
	}
	return "less than a minute";
}

export function localTime(iso: string): string | null {
	const date = new Date(iso);
	if (Number.isNaN(date.getTime())) return null;
	return new Intl.DateTimeFormat(undefined, {
		hour: "numeric",
		minute: "2-digit",
	}).format(date);
}

export function day(iso: string): string {
	return new Intl.DateTimeFormat("en-GB", {
		day: "numeric",
		month: "short",
		year: "numeric",
	}).format(new Date(iso));
}

export function count(n: number, noun: string): string {
	const num = new Intl.NumberFormat("en").format(n);
	return `${num} ${noun}${n === 1 ? "" : "s"}`;
}
