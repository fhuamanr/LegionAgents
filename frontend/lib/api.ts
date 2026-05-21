import { mockDashboardSnapshot } from "./mock-data";
import type { DashboardSnapshot } from "./types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

async function requestJson<T>(path: string): Promise<T> {
  if (!apiBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: {
      Accept: "application/json",
    },
    next: { revalidate: 10 },
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as T;
}

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  if (!apiBaseUrl) {
    return mockDashboardSnapshot;
  }

  try {
    return await requestJson<DashboardSnapshot>("/dashboard/snapshot");
  } catch {
    return mockDashboardSnapshot;
  }
}
