// API contract of GET /api/repos/{owner}/{repo}/report (D-108).

export type Level = "low" | "medium" | "high";
export type Status = "green" | "amber" | "red";
export type SignalId =
	| "liveness"
	| "bus_factor"
	| "responsiveness"
	| "releases"
	| "license";

export type Signal = {
	id: SignalId;
	status: Status;
	summary: string;
	evidence: Record<string, unknown>;
};

export type Report = {
	repo: string;
	verdict: { level: Level; reason: string };
	signals: Signal[];
	context: {
		stars: number;
		forks: number;
		language: string | null;
		created_at: string;
		pushed_at: string;
		archived: boolean;
		description: string | null;
	};
	meta: {
		cached: boolean;
		stale: boolean;
		fetched_at: string;
		// null when served from fresh cache (no GitHub call)
		rate_limit: { remaining: number; reset_at: string } | null;
	};
};

export type ApiErrorCode =
	| "invalid_repo"
	| "not_found"
	| "empty_repo"
	| "rate_limited"
	| "upstream_error";

export type ApiError = {
	error: { code: ApiErrorCode; message: string; reset_at?: string };
};
