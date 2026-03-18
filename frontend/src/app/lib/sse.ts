import { APP_CONFIG, apiPath } from "./config";
import { getMockStreamFrames } from "./mock";
import { JobStatus } from "./types";

export interface JobStreamHandlers {
  onStatus: (job: JobStatus) => void;
  onLog: (line: string, level?: "INFO" | "ERROR") => void;
  onDone: (status: JobStatus["status"]) => void;
  onArtifactReady?: (payload: Record<string, unknown>) => void;
  onModeChange?: (isMock: boolean, reason?: string) => void;
}

export interface JobStreamOptions {
  paperId: string;
  jobId: string;
  runId: string;
  forceMock?: boolean;
  initialStatus?: JobStatus;
}

export interface StreamSubscription {
  close: () => void;
}

function tryParseJson(data: string): Record<string, unknown> | undefined {
  try {
    const parsed = JSON.parse(data);
    if (parsed && typeof parsed === "object") {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return undefined;
  }
  return undefined;
}

export function connectJobStream(options: JobStreamOptions, handlers: JobStreamHandlers): StreamSubscription {
  if (options.forceMock) {
    handlers.onModeChange?.(true, "stream forced to mock");
    return connectMockStream(options, handlers);
  }

  const endpoint = apiPath(`/jobs/${encodeURIComponent(options.jobId)}/events`);

  let closed = false;
  let source: EventSource | null = null;
  let reconnectAttempt = 0;
  let reconnectTimer: number | null = null;
  let hasReceivedData = false;
  let mockSubscription: StreamSubscription | null = null;

  const stop = () => {
    closed = true;
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer);
    }
    if (source) {
      source.close();
      source = null;
    }
    if (mockSubscription) {
      mockSubscription.close();
      mockSubscription = null;
    }
  };

  const connect = () => {
    if (closed) {
      return;
    }

    source = new EventSource(endpoint);

    source.onopen = () => {
      reconnectAttempt = 0;
    };

    source.addEventListener("status", (event) => {
      const message = event as MessageEvent;
      const payload = tryParseJson(message.data);
      if (!payload) {
        return;
      }
      hasReceivedData = true;
      handlers.onModeChange?.(false);
      handlers.onStatus({
        job_id: String(payload.job_id ?? options.jobId),
        paper_id: String(payload.paper_id ?? options.paperId),
        run_id: String(payload.run_id ?? options.runId),
        persona_id: payload.persona_id ? String(payload.persona_id) : undefined,
        reasoning_persona: payload.reasoning_persona ? String(payload.reasoning_persona) as JobStatus["reasoning_persona"] : undefined,
        profile_id: payload.profile_id ? String(payload.profile_id) : undefined,
        status: String(payload.status ?? "running") as JobStatus["status"],
        progress: Number(payload.progress ?? 0),
        stage: payload.stage ? String(payload.stage) : undefined,
        error_message: payload.error_message ? String(payload.error_message) : null,
        created_at: payload.created_at ? String(payload.created_at) : undefined,
        started_at: payload.started_at ? String(payload.started_at) : undefined,
        finished_at: payload.finished_at ? String(payload.finished_at) : undefined,
      });
    });

    source.addEventListener("log", (event) => {
      const message = event as MessageEvent;
      hasReceivedData = true;
      const payload = tryParseJson(message.data);
      if (payload) {
        handlers.onLog(
          String(payload.message ?? payload.raw ?? message.data),
          String(payload.level ?? "INFO").toUpperCase() === "ERROR" ? "ERROR" : "INFO",
        );
      } else {
        handlers.onLog(message.data, "INFO");
      }
    });

    source.addEventListener("artifact_ready", (event) => {
      const message = event as MessageEvent;
      const payload = tryParseJson(message.data);
      if (payload) {
        handlers.onArtifactReady?.(payload);
      }
    });

    source.addEventListener("done", (event) => {
      const message = event as MessageEvent;
      const status = String(message.data || "completed") as JobStatus["status"];
      handlers.onDone(status);
      stop();
    });

    source.onerror = () => {
      if (closed) {
        return;
      }

      if (source) {
        source.close();
        source = null;
      }

      reconnectAttempt += 1;

      if (!hasReceivedData && reconnectAttempt >= 2) {
        if (APP_CONFIG.strictApi) {
          handlers.onLog("SSE unavailable in strict API mode", "ERROR");
          stop();
          return;
        }
        handlers.onModeChange?.(true, "sse unavailable, switched to mock stream");
        mockSubscription = connectMockStream(options, handlers);
        closed = true;
        return;
      }

      const backoff = APP_CONFIG.sseBackoffMs[Math.min(reconnectAttempt - 1, APP_CONFIG.sseBackoffMs.length - 1)];
      reconnectTimer = window.setTimeout(connect, backoff);
    };
  };

  connect();

  return { close: stop };
}

function connectMockStream(options: JobStreamOptions, handlers: JobStreamHandlers): StreamSubscription {
  let closed = false;
  const frames = getMockStreamFrames(options.paperId, options.jobId, options.runId);
  let index = 0;

  const seedStatus: JobStatus =
    options.initialStatus ?? {
      job_id: options.jobId,
      paper_id: options.paperId,
      run_id: options.runId,
      status: "queued",
      progress: 0,
      stage: "queued",
      created_at: new Date().toISOString(),
    };

  handlers.onStatus(seedStatus);

  const intervalId = window.setInterval(() => {
    if (closed) {
      window.clearInterval(intervalId);
      return;
    }

    const frame = frames[index];
    if (!frame) {
      window.clearInterval(intervalId);
      return;
    }

    const current: JobStatus = {
      job_id: options.jobId,
      paper_id: options.paperId,
      run_id: options.runId,
      status: frame.status,
      progress: frame.progress,
      stage: frame.stage,
      created_at: seedStatus.created_at,
      started_at: seedStatus.started_at ?? new Date().toISOString(),
      finished_at: frame.status === "completed" || frame.status === "failed" ? new Date().toISOString() : null,
      error_message: frame.status === "failed" ? frame.log : null,
    };

    handlers.onStatus(current);
    handlers.onLog(frame.log, frame.level ?? "INFO");

    if (frame.status === "completed" || frame.status === "failed") {
      handlers.onDone(frame.status);
      window.clearInterval(intervalId);
    }

    index += 1;
  }, 1300);

  return {
    close: () => {
      closed = true;
      window.clearInterval(intervalId);
    },
  };
}
