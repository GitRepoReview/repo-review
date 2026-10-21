import { useEffect, useId, useState } from "react";
import type { Repo } from "./api";
import { age, count, day } from "./format";
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

function show(value: unknown): string {
	return typeof value === "object" && value !== null
		? JSON.stringify(value)
		: String(value);
}

function Tile({
	signal,
	wide,
	grow,
}: {
	signal: Signal;
	wide: boolean;
	grow?: Grow;
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
			className={`rounded-[4px] border border-rule bg-surface p-4 ${wide ? "md:col-span-2" : ""}`}
		>
			<h3 className="flex items-center gap-2 text-body font-semibold">
				<SignalIcon id={signal.id} />
				{NAMES[signal.id]}
			</h3>
			<div
				className={
					wide
						? "mt-3 flex flex-wrap items-center gap-x-6 gap-y-1"
						: "mt-3 space-y-1"
				}
			>
				{value && <p className="text-h2 font-semibold">{value}</p>}
				{status}
				<p className="max-w-[75ch]">{signal.summary}</p>
			</div>
			<details className="mt-3 text-small">
				<summary className="w-fit cursor-pointer rounded-[4px] text-muted">
					Show evidence
				</summary>
				<dl className="mt-2 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
					{Object.entries(signal.evidence).map(([key, value]) => (
						<div key={key} className="contents">
							<dt className="text-muted">{key}</dt>
							<dd className="break-words">{show(value)}</dd>
						</div>
					))}
				</dl>
			</details>
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

function contextLine({ context: c }: ReportData): string {
	return [
		count(c.stars, "star"),
		count(c.forks, "fork"),
		c.language,
		`created ${day(c.created_at)}`,
		c.archived ? "archived" : "not archived",
	]
		.filter(Boolean)
		.join(", ")
		.concat(".");
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
				Checking{" "}
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
			<header
				className={`${PANEL} verdict-panel ${TONES[report.verdict.level]}`}
			>
				<p className="font-mono text-body break-all">{report.repo}</p>
				<h2
					className={`mt-1 flex flex-wrap items-center gap-x-4 gap-y-2 text-h1 font-semibold ${level.text}`}
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
			<div className="mt-6 grid gap-4 md:grid-cols-2">
				{signals.map((s, i) => (
					<Tile
						key={s.id}
						signal={s}
						wide={s.id === "license"}
						grow={animate ? { delay: 300 + i * 40, step: 0 } : undefined}
					/>
				))}
			</div>
			<p className="mt-6 text-small text-muted">{contextLine(report)}</p>
			<section className="mt-10 max-w-[75ch]">
				<h2 className="text-h2 font-semibold">How we judge this</h2>
				<p className="mt-2">
					Five signals answer one question: will someone still maintain this in
					two years?
				</p>
				<p className="mt-2">
					The thresholds are heuristics we chose, not research. Read them, or
					disagree, in{" "}
					<a href={THRESHOLDS_URL} className="underline underline-offset-2">
						thresholds.py
					</a>
					.
				</p>
			</section>
		</>
	);
}
