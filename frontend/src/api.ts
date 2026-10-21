import type { ApiError, ApiErrorCode, Report } from "./types";

export type Repo = { owner: string; repo: string };

// What the UI needs to pick an error message; `network` = no usable API reply.
export type Failure = {
	code: ApiErrorCode | "network";
	resetAt?: string;
};

const ERROR_CODES = new Set<string>([
	"invalid_repo",
	"not_found",
	"empty_repo",
	"rate_limited",
	"upstream_error",
]);

const OWNER = /^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/;
const REPO = /^[A-Za-z0-9._-]{1,100}$/;

// "owner/repo" or a GitHub link (scheme, www, .git, trailing slash, /tree/…, ?query).
export function parseRepo(input: string): Repo | null {
	const text = input.trim().replace(/[?#].*$/, "");
	const url = text.replace(/^https?:\/\//i, "").replace(/^www\./i, "");
	const isLink = /^github\.com\//i.test(url);
	const path = isLink ? url.replace(/^github\.com\//i, "") : text;
	const parts = path.split("/").filter(Boolean);
	if (parts.length < 2 || (!isLink && parts.length > 2)) return null;
	const owner = parts[0];
	const repo = parts[1].replace(/\.git$/i, "");
	if (!OWNER.test(owner) || !REPO.test(repo) || repo === "." || repo === "..") {
		return null;
	}
	return { owner, repo };
}

export async function fetchReport({ owner, repo }: Repo): Promise<Report> {
	let res: Response;
	try {
		res = await fetch(`/api/repos/${owner}/${repo}/report`);
	} catch {
		throw { code: "network" } satisfies Failure;
	}
	const body = await res.json().catch(() => null);
	if (res.ok && body) return body as Report;
	const err = (body as ApiError | null)?.error;
	throw {
		code: err && ERROR_CODES.has(err.code) ? err.code : "network",
		resetAt: err?.reset_at,
	} satisfies Failure;
}
