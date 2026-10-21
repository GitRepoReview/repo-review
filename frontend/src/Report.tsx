import { useEffect, useId, useState } from "react";
import type { Repo } from "./api";
import { age, compact, evidenceRows, monthYear } from "./format";
import { SignalIcon } from "./icons";
import type { Level, Report as ReportData, Signal, SignalId } from "./types";

const THRESHOLDS_URL =
	"https://github.com/GitRepoReview/repo-review/blob/main/backend/analysis/thresholds.py";

const NAMES: Record<SignalId, string> = {
	liveness: "Last commit",
	bus_factor: "One author",
	responsiveness: "Issue response",
	releases: "Releases",
	license: "License",
};

export const LEVELS: Record<Level, { word: string; text: string }> = {
	low: { word: "Low risk", text: "text-ok" },
	medium: { word: "Medium risk", text: "text-watch" },
	high: { word: "High risk", text: "text-risk" },
};

type Look = { word: string; filled: number; fill: string; unknown: boolean };

function look(signal: Signal): Look {
	if (
		signal.status === "amber" &&
		signal.evidence.reason === "insufficient_data"
	) {
		return { word: "Not enough data", filled: 0, fill: "", unknown: true };
	}
	if (signal.status === "green") {
		return { word: "Healthy", filled: 1, fill: "fill-ok", unknown: false };
	}
	if (signal.status === "amber") {
		return { word: "Watch", filled: 2, fill: "fill-watch", unknown: false };
	}
	return { word: "Risk", filled: 3, fill: "fill-risk", unknown: false };
}

const LEVEL_LOOK: Record<Level, Look> = {
	low: { word: "Low risk", filled: 1, fill: "fill-ok", unknown: false },
	medium: {
		word: "Medium risk",
		filled: 2,
		fill: "fill-watch",
		unknown: false,
	},
	high: { word: "High risk", filled: 3, fill: "fill-risk", unknown: false },
};

// S: tile (20×6), L: verdict (32×10); gap 3.
const SIZES = { S: [20, 6], L: [32, 10] } as const;

// `grow`: filled segments grow in from the left, segment i starting at
// `delay + i * step` ms. Only set for a report that has not been shown yet.
type Grow = { delay: number; step: number };

function Meter({
	look: { word, filled, fill, unknown },
	size,
	grow,
}: {
	look: Look;
	size: keyof typeof SIZES;
	grow?: Grow;
}) {
	const hatch = useId().replace(/:/g, "");
	const [w, h] = SIZES[size];
	const width = 3 * w + 6;
	return (
		<svg
			width={width}
			height={h}
			viewBox={`0 0 ${width} ${h}`}
			role="img"
			aria-label={word}
			className="shrink-0"
		>
			{unknown && (
				<defs>
					<pattern
						id={hatch}
						width="3"
						height="3"
						patternUnits="userSpaceOnUse"
						patternTransform="rotate(45)"
					>
						<line
							x1="0"
							y1="0"
							x2="0"
							y2="3"
							strokeWidth="1.5"
							className="stroke-unknown"
						/>
					</pattern>
				</defs>
			)}
			{[0, 1, 2].map((i) => (
				<rect
					key={i}
					x={i * (w + 3)}
					width={w}
					height={h}
					rx="2"
					fill={unknown ? `url(#${hatch})` : undefined}
					style={
						i >= filled && !unknown
							? { fill: "var(--color-rule)" }
							: grow && i < filled
								? { animationDelay: `${grow.delay + i * grow.step}ms` }
								: undefined
					}
					className={
						i < filled ? `${fill}${grow ? " seg-grow" : ""}` : undefined
					}
				/>
			))}
		</svg>
	);
}

const num = new Intl.NumberFormat("en", { maximumFractionDigits: 1 });

function days(n: number): string {
	return `${num.format(n)} ${n === 1 ? "day" : "days"}`;
}

// Headline figure of a tile, from evidence; null when the field is absent.
function keyValue({ id, evidence: e }: Signal): string | null {
	if (e.reason === "insufficient_data") return null;
	switch (id) {
		case "liveness":
			return typeof e.days_since_last_commit === "number"
				? e.days_since_last_commit === 0
					? "Today"
					: days(e.days_since_last_commit)
				: null;
		case "bus_factor":
			return typeof e.top_author_share_pct === "number"
				? `${num.format(e.top_author_share_pct)}%`
				: null;
		case "responsiveness":
			return typeof e.median_close_days === "number"
				? Math.round(e.median_close_days * 10) === 0
					? "< 1 day"
					: days(Math.round(e.median_close_days * 10) / 10)
				: null;
		case "releases":
			return typeof e.days_since_last_release === "number"
				? days(e.days_since_last_release)
				: "None";
		case "license":
			return null;
	}
}

export const evidenceId = (id: SignalId) => `evidence-${id}`;

function Evidence({ signal, open }: { signal: Signal; open: boolean }) {
	return (
		<div
			id={evidenceId(signal.id)}
			hidden={!open}
			className="mt-3 self-start rounded-[4px] bg-paper px-[14px] py-3"
		>
			<dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-4">
				{evidenceRows(signal.evidence).map(({ key, label, value }) => (
					<div
						key={key}
						className="col-span-2 grid grid-cols-subgrid items-baseline border-t border-rule py-1.5 first:border-t-0 first:pt-0 last:pb-0"
					>
						<dt className="text-[13px] text-muted">{label}</dt>
						<dd
							className={`min-w-0 text-small tabular-nums [overflow-wrap:anywhere] ${value.length > 24 ? "text-left" : "text-right"}`}
						>
							{value}
						</dd>
					</div>
				))}
			</dl>
		</div>
	);
}

function Tile({
	signal,
	wide,
	grow,
	open,
}: {
	signal: Signal;
	wide: boolean;
	grow?: Grow;
	open: boolean;
}) {
	const l = look(signal);
	const value = keyValue(signal);
	const status = (
		<p className="flex items-center gap-2 font-semibold">
			<Meter look={l} size="S" grow={grow} />
			{l.word}
		</p>
	);
	return (
		<section
			className={`min-w-0 rounded-[4px] border border-rule bg-surface p-4 mb-4 [overflow-wrap:anywhere] ${wide ? "md:col-span-2" : "md:row-span-5 md:grid md:grid-rows-subgrid"}`}
		>
			<h3 className="flex items-center gap-2 text-body font-semibold">
				<SignalIcon id={signal.id} />
				{NAMES[signal.id]}
			</h3>
			{wide ? (
				<div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1">
					{status}
					<p className="max-w-[75ch]">{signal.summary}</p>
				</div>
			) : (
				<>
					<p
						className={`mt-3 text-h2 font-semibold ${value ? "" : "hidden md:block"}`}
					>
						{value}
					</p>
					<div className="mt-1">{status}</div>
					<p className="mt-1 max-w-[75ch]">{signal.summary}</p>
				</>
			)}
			<Evidence signal={signal} open={open} />
		</section>
	);
}

function freshness({ meta }: ReportData): string {
	const base = meta.cached
		? `Checked ${age(meta.fetched_at)} ago, from cache.`
		: "Checked just now.";
	return meta.rate_limit
		? `${base} ${meta.rate_limit.remaining} of 60 GitHub requests left this hour.`
		: base;
}

function ReportHeader({ repo, context: c }: ReportData) {
	const facts: [string, string][] = [
		["Stars", compact(c.stars)],
		["Forks", compact(c.forks)],
		["Watching", compact(c.watchers)],
		["Open issues & PRs", compact(c.open_issues)],
		["Language", c.language ?? "—"],
		["Created", monthYear(c.created_at)],
		["Last push", `${age(c.pushed_at)} ago`],
	];
	const link =
		"text-accent underline underline-offset-2 [overflow-wrap:anywhere]";
	return (
		<div className="mb-4">
			<div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
				<h2 className="min-w-0 font-mono text-h2 text-ink break-all">{repo}</h2>
				<p className="flex gap-x-4 text-small">
					<a href={c.html_url} className={link}>
						View on GitHub
					</a>
					{c.homepage && (
						<a href={c.homepage} className={link}>
							Homepage
						</a>
					)}
				</p>
			</div>
			{c.description && (
				<p className="mt-1 max-w-[75ch] text-body text-muted [overflow-wrap:anywhere]">
					{c.description}
				</p>
			)}
			<dl className="mt-3 grid grid-cols-2 gap-x-8 gap-y-3 sm:flex sm:flex-wrap">
				{facts.map(([label, value]) => (
					<div key={label} className="min-w-0">
						<dt className="text-[13px] text-muted">{label}</dt>
						<dd className="font-semibold tabular-nums [overflow-wrap:anywhere]">
							{value}
						</dd>
					</div>
				))}
			</dl>
			<p className="mt-3 text-[13px] text-muted">
				Popularity isn't part of the verdict.
			</p>
		</div>
	);
}

const ORDER = Object.keys(NAMES);

const PANEL = "min-h-44 rounded-[4px] border border-rule bg-surface p-6";
const TONES: Record<Level, string> = {
	low: "tone-ok",
	medium: "tone-watch",
	high: "tone-risk",
};

// Reports already shown in this session; a re-render of one does not animate.
const seen = new Set<string>();

export function Waiting({ repo }: { repo: Repo }) {
	return (
		<div className={`${PANEL} border-t-[3px]`}>
			<p>
				Reviewing{" "}
				<span className="font-mono">{`${repo.owner}/${repo.repo}`}</span>…
			</p>
			<svg
				width="102"
				height="10"
				viewBox="0 0 102 10"
				aria-hidden="true"
				className="mt-4"
			>
				{[0, 1, 2].map((i) => (
					<rect
						key={i}
						x={i * 35}
						width="32"
						height="10"
						rx="2"
						className="seg-wait"
						style={{ animationDelay: `${i * 300}ms` }}
					/>
				))}
			</svg>
		</div>
	);
}

export function Report({ report }: { report: ReportData }) {
	const key = `${report.repo}@${report.meta.fetched_at}`;
	const [animate] = useState(() => !seen.has(key));
	useEffect(() => {
		seen.add(key);
	}, [key]);
	const [open, setOpen] = useState(false);
	const level = LEVELS[report.verdict.level];
	const signals = [...report.signals].sort(
		(a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id),
	);
	return (
		<>
			{report.meta.stale && (
				<p className="mb-6 border-l-4 border-watch pl-3 text-small text-muted">
					Showing data from {age(report.meta.fetched_at)} ago — couldn't refresh
					because the hourly GitHub limit is used up.
				</p>
			)}
			<ReportHeader {...report} />
			<header
				className={`${PANEL} verdict-panel ${TONES[report.verdict.level]}`}
			>
				<h2
					className={`flex flex-wrap items-center gap-x-4 gap-y-2 text-h1 font-semibold ${level.text}`}
				>
					{level.word}
					<Meter
						look={LEVEL_LOOK[report.verdict.level]}
						size="L"
						grow={animate ? { delay: 0, step: 90 } : undefined}
					/>
				</h2>
				<p className="mt-2 max-w-[75ch] text-h2">{report.verdict.reason}</p>
				<p className="mt-2 text-small text-muted">{freshness(report)}</p>
			</header>
			<div className="mt-6 flex justify-end">
				<button
					type="button"
					onClick={() => setOpen(!open)}
					aria-expanded={open}
					aria-controls={ORDER.map((id) => evidenceId(id as SignalId)).join(
						" ",
					)}
					className="flex h-9 cursor-pointer items-center gap-2 rounded-[6px] border border-rule bg-surface px-3 text-small font-semibold text-ink hover:border-unknown"
				>
					{open ? "Hide evidence" : "Show evidence"}
					<svg
						width="16"
						height="16"
						viewBox="0 0 20 20"
						fill="none"
						stroke="currentColor"
						strokeWidth="1.5"
						strokeLinecap="round"
						strokeLinejoin="round"
						aria-hidden="true"
						className={`text-muted ${open ? "rotate-180" : ""}`}
					>
						<path d="M5 8l5 5 5-5" />
					</svg>
				</button>
			</div>
			<div className="mt-2 grid grid-cols-1 gap-x-4 md:grid-cols-2">
				{signals.map((s, i) => (
					<Tile
						key={s.id}
						signal={s}
						wide={s.id === "license"}
						open={open}
						grow={animate ? { delay: 300 + i * 40, step: 0 } : undefined}
					/>
				))}
			</div>
			<section className="mt-10 max-w-[75ch]">
				<h2 className="text-h2 font-semibold">How we judge this</h2>
				<p className="mt-2">
					Five signals answer one question: will someone still maintain this in
					two years?
				</p>
				<p className="mt-2">
					The thresholds are heuristics we chose, not research. Read them, or
					disagree, in{" "}
					<a
						href={THRESHOLDS_URL}
						className="text-accent underline underline-offset-2"
					>
						thresholds.py
					</a>
					.
				</p>
			</section>
		</>
	);
}
