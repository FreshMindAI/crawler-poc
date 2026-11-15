"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  let epoch = 0;
  let key = "";
  let jobId = "";
  let lastJob = null;
  let timer = null;
  let deadline = 0;
  let bodyOffset = 0;
  let bodyTotal = 0;
  let jobs = new Map();
  let rows = new Map();
  let batch = false;
  let pollCursor = 0;
  let viewVersion = 0;
  const pageSize = 16000;

  function inputMode() {
    const multiple = $("input-mode").value === "multiple";
    $("single-label").hidden = multiple;
    $("url").hidden = multiple;
    $("url").disabled = multiple;
    $("url").required = !multiple;
    $("multiple-field").hidden = !multiple;
    $("urls").disabled = !multiple;
    $("urls").required = multiple;
    $("submit").textContent = multiple ? "Inspect pages \u2192" : "Inspect page \u2192";
  }

  function message(text = "") {
    $("message").textContent = text;
    $("message").hidden = !text;
  }

  function busy(value) {
    for (const id of ["submit", "url", "urls", "input-mode", "api-key", "top-k"]) $(id).disabled = value;
    if (value) $("submit").textContent = "Inspecting...";
    else inputMode();
  }

  async function request(path, options = {}) {
    const response = await fetch(path, {
      ...options,
      headers: { "X-API-Key": key, ...options.headers },
      cache: "no-store",
      credentials: "omit",
      redirect: "error",
      signal: AbortSignal.timeout(15000),
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error("API key not accepted. Check the key and try again.");
      if (response.status === 429) throw new Error("Request limit reached. Wait at least 60 seconds before resuming.");
      if (response.status === 422) throw new Error("The URL or request is not supported. Use a public HTTP or HTTPS page.");
      if (response.status === 404) throw new Error("The requested job or content is no longer available.");
      throw new Error(`Request failed (HTTP ${response.status}). Try again or check the API service.`);
    }
    return response;
  }

  function errorText(error) {
    if (error.name === "TimeoutError" || error.name === "AbortError") {
      return "The API request timed out. The crawl may still be running; resume monitoring to check it.";
    }
    return error instanceof TypeError ? "Cannot reach the API. Check your connection and service." : error.message;
  }

  function stop() {
    clearTimeout(timer);
    timer = null;
    busy(false);
  }

  function field(container, label, value) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value === null || value === undefined || value === "" ? "Not provided" : String(value);
    row.append(term, description);
    container.append(row);
  }

  function raw(job) {
    lastJob = job;
    $("json-panel").hidden = false;
    $("json-output").textContent = JSON.stringify(job, null, 2);
  }

  function updateBatch() {
    const values = [...jobs.values()];
    const finished = values.filter((job) => job.status === "terminal");
    const successes = finished.filter((job) => job.result?.outcome === "success").length;
    $("batch-summary").textContent = `${finished.length} of ${values.length} finished: ${successes} extracted, ${finished.length - successes} failed or canceled.`;
    for (const job of values) {
      const row = rows.get(job.id);
      if (!row) continue;
      row.button.setAttribute("aria-pressed", String(job.id === jobId));
      row.status.textContent = job.status === "terminal" ? (job.result?.outcome || "unknown") : job.status;
    }
  }

  function showJob(job) {
    $("job-id").textContent = job.id;
    raw(job);
    const result = job.result || {};
    $("cancel").hidden = job.status === "terminal";
    if (job.status === "terminal") {
      if (result.outcome === "success") {
        $("progress-heading").textContent = "Extraction complete";
        $("progress-detail").textContent = "The result below belongs to this crawl.";
        render(job);
      } else {
        $("results").hidden = true;
        $("progress-heading").textContent = result.outcome === "canceled" ? "Crawl canceled" : "No extraction returned";
        $("progress-detail").textContent = "No successful page content is being shown.";
        message([
          `Outcome: ${result.outcome || "unknown"}.`,
          result.reason ? `Reason: ${result.reason}.` : "",
          result.http_status ? `HTTP ${result.http_status}.` : "",
          result.metadata?.failure_stage ? `Stage: ${result.metadata.failure_stage}.` : "",
        ].filter(Boolean).join(" "));
      }
    } else {
      $("progress-heading").textContent = job.status === "running" ? "Crawling page" : "Waiting for a worker";
      $("progress-detail").textContent = `Attempts: ${job.attempts || 0}. ${job.status === "running" ? "Fetching and extracting; browser fallback may take longer." : "Queued or waiting for retry. Make sure a separate crawler worker is running."}`;
    }
  }

  function selectJob(identifier) {
    ++viewVersion;
    jobId = identifier;
    lastJob = null;
    bodyOffset = 0;
    $("body-text").textContent = "";
    $("more").disabled = false;
    $("results").hidden = true;
    $("json-panel").hidden = true;
    message();
    showJob(jobs.get(identifier));
    updateBatch();
  }

  function createBatchRows() {
    $("batch-list").replaceChildren();
    rows = new Map();
    if (!batch) return;
    for (const job of jobs.values()) {
      const item = document.createElement("li");
      const button = document.createElement("button");
      const label = document.createElement("span");
      const status = document.createElement("small");
      button.type = "button";
      button.setAttribute("aria-label", `View ${job.url}`);
      button.addEventListener("click", () => selectJob(job.id));
      label.textContent = job.url;
      button.append(label, status);
      item.append(button);
      $("batch-list").append(item);
      rows.set(job.id, { button, status });
    }
  }

  function render(job) {
    const result = job.result || {};
    raw(job);
    $("empty").hidden = true;
    $("results").hidden = false;
    $("result-title").textContent = result.title || "Untitled page";
    $("result-url").textContent = result.final_url || job.url;
    $("description").textContent = result.description || "No description was provided by this page.";
    $("facts").replaceChildren();
    const duration = result.timings_ms?.total;
    for (const [label, value] of [
      ["Page type", result.page_type], ["HTTP status", result.http_status],
      ["Fetch method", result.fetch_method], ["Words", result.word_count],
      ["Pipeline time", duration === undefined ? null : `${(duration / 1000).toFixed(2)} s`],
    ]) field($("facts"), label, value);
    $("metadata").replaceChildren();
    for (const [label, value] of [
      ["Language", result.language], ["Author", result.author],
      ["Published (source value)", result.published_time],
      ["Canonical candidate", result.canonical_candidate],
      ["Headings", (result.headings || []).join("\n")],
      ["Classification evidence", (result.page_type_evidence || []).join(", ")],
    ]) field($("metadata"), label, value);
    $("topics").replaceChildren();
    for (const topic of result.topics || []) {
      const item = document.createElement("li");
      const text = document.createElement("span");
      const detail = document.createElement("small");
      text.textContent = topic.phrase;
      const score = topic.ranking_score ?? topic.raw_score;
      detail.textContent = `${typeof score === "number" ? score.toPrecision(3) : "No score"} | ${topic.evidence || topic.method || "Local ranking"}`;
      item.append(text, detail);
      $("topics").append(item);
    }
    if (!result.topics?.length) {
      const item = document.createElement("li");
      item.textContent = "No topics returned.";
      $("topics").append(item);
    }
    const warnings = result.warnings || [];
    $("warnings").hidden = warnings.length === 0;
    $("warnings").textContent = warnings.length ? `Extraction notes: ${warnings.join(", ")}` : "";
    $("body-text").textContent = result.body_preview || "No readable body preview returned.";
    bodyOffset = 0;
    bodyTotal = result.body_characters || 0;
    $("body-count").textContent = `${bodyTotal.toLocaleString()} characters reported`;
    $("more").hidden = !result.body_ref || !bodyTotal;
    $("more").textContent = "Load readable text";
    $("result-title").focus();
  }

  async function poll(run) {
    if (run !== epoch) return;
    const pending = [...jobs.values()].filter((job) => job.status !== "terminal");
    if (!pending.length) {
      stop();
      $("resume").hidden = true;
      return;
    }
    const identifier = pending[pollCursor++ % pending.length].id;
    try {
      const job = await (await request(`/v1/crawls/${encodeURIComponent(identifier)}`)).json();
      if (run !== epoch) return;
      jobs.set(identifier, job);
      if (identifier === jobId) showJob(job);
      updateBatch();
      if ([...jobs.values()].every((item) => item.status === "terminal")) {
        stop();
        $("resume").hidden = true;
        return;
      }
      if (Date.now() > deadline) {
        stop();
        $("resume").hidden = false;
        message("Monitoring paused after five minutes. Submitted jobs continue on the server; resume to check them.");
        return;
      }
      timer = setTimeout(() => poll(run), batch ? 1500 : 4000);
    } catch (error) {
      if (run !== epoch) return;
      stop();
      $("resume").hidden = false;
      message(errorText(error));
    }
  }

  $("crawl-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const multiple = $("input-mode").value === "multiple";
    const urls = multiple ? $("urls").value.trim().split(/\s+/u) : [$("url").value.trim()];
    let payload;
    try {
      if (urls.length > 100) throw new Error("Submit at most 100 URLs at a time.");
      for (const url of urls) {
        let parsed;
        try { parsed = new URL(url); } catch { throw new Error("Each entry must be an absolute HTTP or HTTPS URL."); }
        if (!/^https?:\/\//i.test(url) || !["http:", "https:"].includes(parsed.protocol)) {
          throw new Error("Each entry must be an absolute HTTP or HTTPS URL.");
        }
      }
      payload = JSON.stringify({
        ...(multiple ? { urls } : { url: urls[0] }),
        top_k: Number($("top-k").value),
        generation: `ui-${crypto.randomUUID()}`,
      });
      if (new TextEncoder().encode(payload).length > 65536) {
        throw new Error("This URL list exceeds the 64 KiB request limit. Submit a smaller batch.");
      }
    } catch (error) {
      message(errorText(error));
      return;
    }
    const run = ++epoch;
    ++viewVersion;
    stop();
    key = $("api-key").value.trim();
    jobId = "";
    lastJob = null;
    jobs = new Map();
    batch = multiple;
    pollCursor = 0;
    message();
    for (const id of ["results", "json-panel", "empty", "resume", "cancel", "batch"]) $(id).hidden = true;
    $("progress").hidden = false;
    $("progress-heading").textContent = multiple ? "Submitting URLs" : "Submitting URL";
    $("progress-detail").textContent = "Creating crawl jobs.";
    $("job-id").textContent = "Pending";
    busy(true);
    try {
      const response = await request("/v1/crawls", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      const submitted = await response.json();
      if (run !== epoch) return;
      submitted.job_ids.forEach((identifier, index) => {
        if (!jobs.has(identifier)) jobs.set(identifier, {
          id: identifier, url: urls[index], status: "queued", attempts: 0, result: null,
        });
      });
      createBatchRows();
      $("batch").hidden = !batch;
      selectJob(submitted.job_ids[0]);
      deadline = Date.now() + 300000;
      await poll(run);
    } catch (error) {
      if (run !== epoch) return;
      stop();
      $("progress-heading").textContent = "Submission not confirmed";
      $("progress-detail").textContent = "If the API timed out, check your jobs before submitting again.";
      message(errorText(error));
    }
  });

  $("resume").addEventListener("click", () => {
    key = $("api-key").value.trim();
    if (!key) { message("Enter the API key before resuming."); $("api-key").focus(); return; }
    message();
    $("resume").hidden = true;
    busy(true);
    deadline = Date.now() + 300000;
    poll(++epoch);
  });

  $("cancel").addEventListener("click", async () => {
    const run = ++epoch;
    const identifier = jobId;
    stop();
    busy(true);
    $("cancel").disabled = true;
    try {
      await request(`/v1/crawls/${encodeURIComponent(identifier)}/cancel`, { method: "POST" });
      if (run !== epoch) return;
      message();
      const job = await (await request(`/v1/crawls/${encodeURIComponent(identifier)}`)).json();
      if (run !== epoch) return;
      jobs.set(identifier, job);
      if (identifier === jobId) showJob(job);
      updateBatch();
      await poll(run);
    } catch (error) {
      if (run !== epoch) return;
      stop();
      $("resume").hidden = false;
      message(errorText(error));
    } finally {
      if (run === epoch) $("cancel").disabled = false;
    }
  });

  $("more").addEventListener("click", async () => {
    const run = epoch;
    const view = viewVersion;
    const identifier = jobId;
    $("more").disabled = true;
    try {
      const response = await request(`/v1/crawls/${encodeURIComponent(identifier)}/content?offset=${bodyOffset}&limit=${pageSize}`);
      const text = await response.text();
      if (run !== epoch || view !== viewVersion) return;
      if (bodyOffset === 0) $("body-text").textContent = "";
      $("body-text").append(document.createTextNode(text));
      const characters = Array.from(text).length;
      bodyOffset += characters;
      $("body-count").textContent = `${bodyOffset.toLocaleString()} of ${bodyTotal.toLocaleString()} characters loaded`;
      $("more").hidden = characters < pageSize || bodyOffset >= bodyTotal || bodyOffset > 250000;
      $("more").textContent = "Load more text";
      if (bodyOffset > 250000 && bodyOffset < bodyTotal) {
        $("body-count").textContent += " (viewer limit reached)";
      }
    } catch (error) {
      if (run === epoch && view === viewVersion) message(errorText(error));
    } finally {
      if (run === epoch && view === viewVersion) $("more").disabled = false;
    }
  });

  function download(value, filename) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  $("download").addEventListener("click", () => {
    if (lastJob) download(lastJob, "crawl-result.json");
  });
  $("download-all").addEventListener("click", () => download([...jobs.values()], "crawl-batch.json"));
  $("input-mode").addEventListener("change", inputMode);

  $("clear-workspace").addEventListener("click", () => {
    ++epoch;
    ++viewVersion;
    stop();
    key = "";
    jobId = "";
    lastJob = null;
    jobs = new Map();
    rows = new Map();
    $("crawl-form").reset();
    inputMode();
    $("cancel").disabled = false;
    $("batch-list").replaceChildren();
    $("json-output").textContent = "";
    $("body-text").textContent = "";
    for (const id of ["progress", "results", "json-panel", "batch"]) $(id).hidden = true;
    $("empty").hidden = false;
    message("Workspace and key cleared. Any submitted job continues unless you canceled it.");
    $("api-key").focus();
  });
})();
