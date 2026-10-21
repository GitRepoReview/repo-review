import type { ReactNode } from "react";
import type { SignalId } from "./types";

const paths: Record<SignalId, ReactNode> = {
	liveness: (
		<>
			<path d="M2 10h5M13 10h5" />
			<circle cx="10" cy="10" r="3" />
		</>
	),
	bus_factor: (
		<>
			<circle cx="10" cy="7" r="3" />
			<path d="M3.5 17c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6" />
		</>
	),
	responsiveness: <path d="M3 4.5h14v9H8.5L5 16.5v-3H3z" />,
	releases: (
		<>
			<path d="M3 3h6.5l7.5 7.5-6.5 6.5L3 9.5z" />
			<circle cx="6.5" cy="6.5" r="1" />
		</>
	),
	license: (
		<>
			<path d="M5 2.5h7l4 4v11H5z" />
			<path d="M12 2.5v4h4" />
		</>
	),
};

export function SignalIcon({ id }: { id: SignalId }) {
	return (
		<svg
			width="20"
			height="20"
			viewBox="0 0 20 20"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.5"
			strokeLinecap="round"
			strokeLinejoin="round"
			aria-hidden="true"
			className="shrink-0 text-muted"
		>
			{paths[id]}
		</svg>
	);
}
