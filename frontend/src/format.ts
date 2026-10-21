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

export function compact(n: number): string {
	return new Intl.NumberFormat("en", {
		notation: "compact",
		maximumFractionDigits: 1,
	}).format(n);
}

export function monthYear(iso: string): string {
	return new Intl.DateTimeFormat("en-GB", {
		month: "short",
		year: "numeric",
	}).format(new Date(iso));
}

export type EvidenceRow = { key: string; label: string; value: string };

const EVIDENCE_LABELS: Record<string, string> = {
	days_since_last_commit: "Days since last commit",
	archived: "Archived",
	human_commits: "Human commits",
	bot_commits: "Bot commits (excluded)",
	merge_commits: "Merge commits (excluded)",
	sample_commits: "Commits sampled",
	top_author: "Top author",
	top_author_share_pct: "Top author share",
	closed_count: "Issues closed (90 days)",
	median_close_days: "Median time to close",
	open_issues_count: "Open issues and PRs",
	days_since_last_release: "Days since last release",
	tag_name: "Latest release tag",
	spdx_id: "SPDX identifier",
};

// "some_key" -> "Some key"
function sentenceCase(key: string): string {
	const text = key.replaceAll("_", " ");
	return text.charAt(0).toUpperCase() + text.slice(1);
}

function localDate(date: Date, year: boolean): string {
	return new Intl.DateTimeFormat("en-GB", {
		day: "numeric",
		month: "short",
		...(year ? { year: "numeric" } : {}),
		hour: "2-digit",
		minute: "2-digit",
		hour12: false,
	})
		.format(date)
		.replace(",", "");
}

// "21 Oct 2026 15:19 – 21 Oct 17:41": the year is shown when it differs
// between the ends or is not the current one.
export function sampleWindow(
	oldest: string,
	newest: string,
	now = new Date(),
): string {
	const a = new Date(oldest);
	const b = new Date(newest);
	const differ = a.getFullYear() !== b.getFullYear();
	const current = now.getFullYear();
	return `${localDate(a, differ || a.getFullYear() !== current)} – ${localDate(b, differ || b.getFullYear() !== current)}`;
}

function evidenceValue(key: string, value: unknown): string {
	if (key === "spdx_id" && value === null) return "Not found";
	if (value === null || value === undefined) return "—";
	if (typeof value === "boolean") return value ? "Yes" : "No";
	if (key === "top_author_share_pct") return `${value}%`;
	if (key === "median_close_days" && typeof value === "number") {
		if (value === 0) return "< 1 day";
		return `${value} ${value === 1 ? "day" : "days"}`;
	}
	return typeof value === "object" ? JSON.stringify(value) : String(value);
}

// Human-readable rows for the evidence block. `reason` is internal and left out.
export function evidenceRows(evidence: Record<string, unknown>): EvidenceRow[] {
	const rows: EvidenceRow[] = [];
	for (const [key, value] of Object.entries(evidence)) {
		if (key === "reason" || key === "sample_newest") continue;
		if (key === "sample_oldest") {
			const { sample_oldest: a, sample_newest: b } = evidence;
			rows.push({
				key,
				label: "Sample window",
				value:
					typeof a === "string" && typeof b === "string"
						? sampleWindow(a, b)
						: "—",
			});
			continue;
		}
		rows.push({
			key,
			label: EVIDENCE_LABELS[key] ?? sentenceCase(key),
			value: evidenceValue(key, value),
		});
	}
	return rows;
}
