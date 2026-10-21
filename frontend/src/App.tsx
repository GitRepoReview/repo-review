import {
	type FormEvent,
	type MouseEvent,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { type Failure, fetchReport, parseRepo, type Repo } from "./api";
import { localTime } from "./format";
import { LEVELS, Report, Waiting } from "./Report";
import type { Report as ReportData } from "./types";

const WAIT_MS = 250;
const SITE = "RepoReview";

const EXAMPLES = ["pallets/flask", "request/request", "sindresorhus/p-map"];

type State =
	| { kind: "idle" }
	| { kind: "report"; report: ReportData }
	| { kind: "error"; failure: Failure; repo: Repo | null };

function Examples({ onPick }: { onPick: (slug: string) => void }) {
	return (
		<p className="flex flex-wrap items-baseline gap-x-4 gap-y-1 text-small text-muted">
			Try:
			{EXAMPLES.map((slug) => (
				<button
					key={slug}
					type="button"
					onClick={() => onPick(slug)}
					className="cursor-pointer rounded-[4px] text-ink underline underline-offset-2"
				>
					{slug}
				</button>
			))}
		</p>
	);
}

function errorMessage({ code, resetAt }: Failure, repo: Repo | null): string {
	const slug = repo ? `${repo.owner}/${repo.repo}` : "that name";
	switch (code) {
		case "invalid_repo":
			return "That doesn't look like owner/repo or a GitHub link.";
		case "not_found":
			return `No public repository at ${slug}. Check the spelling.`;
		case "empty_repo":
			return "This repository has no commits yet, so there's nothing to judge.";
		case "rate_limited": {
			const time = resetAt ? localTime(resetAt) : null;
			return `This server has used its GitHub requests for the hour. Try again${time ? ` after ${time}` : ""}, or open a repo that's already cached.`;
		}
		case "upstream_error":
			return "GitHub didn't respond. Try again in a minute.";
		default:
			return "Something went wrong. Try again in a minute.";
	}
}

function repoParam(): string | null {
	return new URLSearchParams(location.search).get("repo");
}

// /?repo=owner/repo — a query parameter, so the server only ever serves "/".
function repoUrl(text: string): string {
	return `/?repo=${encodeURIComponent(text).replaceAll("%2F", "/")}`;
}

function navigate(url: string) {
	if (url !== location.pathname + location.search) {
		history.pushState(null, "", url);
	}
}

function pageTitle(
	state: State,
	pending: Repo | null,
	waiting: boolean,
): string {
	if (pending && waiting) {
		return `Checking ${pending.owner}/${pending.repo}… | ${SITE}`;
	}
	switch (state.kind) {
		case "report":
			return `${state.report.repo}: ${LEVELS[state.report.verdict.level].word} | ${SITE}`;
		case "error":
			return state.failure.code === "not_found" && state.repo
				? `${state.repo.owner}/${state.repo.repo}: not found | ${SITE}`
				: `Error | ${SITE}`;
		default:
			return SITE;
	}
}

export default function App() {
	const [input, setInput] = useState("");
	const [state, setState] = useState<State>({ kind: "idle" });
	// The repo being fetched; `waiting` flips on only if it takes > WAIT_MS,
	// so cached answers replace the old result without a flash of panel.
	const [pending, setPending] = useState<Repo | null>(null);
	const [waiting, setWaiting] = useState(false);
	const loading = pending !== null;
	// Only the latest request may touch the screen (Back/Forward can overtake).
	const latest = useRef(0);
	const started = useRef(false);

	const reset = useCallback(() => {
		latest.current++;
		setInput("");
		setPending(null);
		setWaiting(false);
		setState({ kind: "idle" });
	}, []);

	const load = useCallback(async (text: string, push: boolean) => {
		const id = ++latest.current;
		const repo = parseRepo(text);
		const slug = repo ? `${repo.owner}/${repo.repo}` : text.trim();
		if (push) navigate(repoUrl(slug));
		setInput(slug);
		setWaiting(false);
		if (!repo) {
			setPending(null);
			setState({
				kind: "error",
				failure: { code: "invalid_repo" },
				repo: null,
			});
			return;
		}
		setPending(repo);
		const timer = setTimeout(() => {
			if (id === latest.current) setWaiting(true);
		}, WAIT_MS);
		let next: State;
		try {
			next = { kind: "report", report: await fetchReport(repo) };
		} catch (failure) {
			next = { kind: "error", failure: failure as Failure, repo };
		}
		clearTimeout(timer);
		if (id !== latest.current) return;
		setState(next);
		setWaiting(false);
		setPending(null);
	}, []);

	useEffect(() => {
		const onPop = () => {
			const param = repoParam();
			if (param) load(param, false);
			else reset();
		};
		window.addEventListener("popstate", onPop);
		return () => window.removeEventListener("popstate", onPop);
	}, [load, reset]);

	// Opened on /?repo=…: run it once (a ref survives StrictMode's double effect).
	useEffect(() => {
		if (started.current) return;
		started.current = true;
		const text = repoParam();
		if (text) load(text, false);
	}, [load]);

	useEffect(() => {
		document.title = pageTitle(state, pending, waiting);
	}, [state, pending, waiting]);

	function onSubmit(e: FormEvent) {
		e.preventDefault();
		if (!loading) load(input, true);
	}

	function pick(slug: string) {
		if (!loading) load(slug, true);
	}

	function home(e: MouseEvent<HTMLAnchorElement>) {
		if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
			return;
		}
		e.preventDefault();
		navigate("/");
		reset();
	}

	return (
		<main className="mx-auto max-w-[760px] px-4 py-10 md:py-12">
			<header>
				<p className="font-semibold">
					<a href="/" onClick={home} className="hover:underline">
						{SITE}
					</a>
				</p>
				<h1 className="mt-6 text-h1 font-semibold">
					Will we regret depending on this?
				</h1>
				<p className="mt-2 max-w-[75ch] text-muted">
					Checks who will maintain an open-source dependency two years from now.
				</p>
			</header>
			<form onSubmit={onSubmit} className="mt-6 flex gap-2">
				<label htmlFor="repo" className="sr-only">
					GitHub repository, as owner/repo or a link
				</label>
				<input
					id="repo"
					value={input}
					onChange={(e) => setInput(e.target.value)}
					placeholder="owner/repo or GitHub link"
					autoComplete="off"
					spellCheck={false}
					autoCapitalize="off"
					className="min-w-0 flex-1 rounded-[6px] border border-rule bg-surface px-3 py-2 text-body placeholder:text-muted"
				/>
				<button
					type="submit"
					disabled={loading}
					className="shrink-0 cursor-pointer rounded-[6px] bg-ink px-4 py-2 text-body font-semibold text-surface disabled:cursor-default disabled:bg-muted"
				>
					{loading ? "Checking…" : "Check repo"}
				</button>
			</form>

			<div aria-live="polite" className="mt-12">
				{pending && waiting && <Waiting repo={pending} />}
				{!(pending && waiting) && state.kind === "idle" && (
					<div className="space-y-2">
						<p className="max-w-[75ch]">
							Paste a GitHub repository to see whether anyone will keep
							maintaining it.
						</p>
						<Examples onPick={pick} />
					</div>
				)}
				{!(pending && waiting) && state.kind === "error" && (
					<div className="space-y-2">
						<p className="max-w-[75ch]">
							{errorMessage(state.failure, state.repo)}
						</p>
						{state.failure.code === "rate_limited" && (
							<Examples onPick={pick} />
						)}
					</div>
				)}
				{!(pending && waiting) && state.kind === "report" && (
					<div>
						<Report
							key={`${state.report.repo}@${state.report.meta.fetched_at}`}
							report={state.report}
						/>
					</div>
				)}
			</div>
		</main>
	);
}
