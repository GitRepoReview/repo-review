import { type FormEvent, useState } from "react";
import { type Failure, fetchReport, parseRepo, type Repo } from "./api";
import { localTime } from "./format";
import { Report, Waiting } from "./Report";
import type { Report as ReportData } from "./types";

const WAIT_MS = 250;

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

export default function App() {
	const [input, setInput] = useState("");
	const [state, setState] = useState<State>({ kind: "idle" });
	// The repo being fetched; `waiting` flips on only if it takes > WAIT_MS,
	// so cached answers replace the old result without a flash of panel.
	const [pending, setPending] = useState<Repo | null>(null);
	const [waiting, setWaiting] = useState(false);
	const loading = pending !== null;

	async function check(text: string) {
		const repo = parseRepo(text);
		if (!repo) {
			setState({
				kind: "error",
				failure: { code: "invalid_repo" },
				repo: null,
			});
			return;
		}
		setPending(repo);
		const timer = setTimeout(() => setWaiting(true), WAIT_MS);
		try {
			setState({ kind: "report", report: await fetchReport(repo) });
		} catch (failure) {
			setState({ kind: "error", failure: failure as Failure, repo });
		} finally {
			clearTimeout(timer);
			setWaiting(false);
			setPending(null);
		}
	}

	function onSubmit(e: FormEvent) {
		e.preventDefault();
		if (!loading) check(input);
	}

	function pick(slug: string) {
		setInput(slug);
		if (!loading) check(slug);
	}

	return (
		<main className="mx-auto max-w-[760px] px-4 py-10 md:py-12">
			<header>
				<p className="font-semibold">RepoReview</p>
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
