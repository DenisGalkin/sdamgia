const form = document.querySelector("#answer-form");
const input = document.querySelector("#test-number");
const submitButton = document.querySelector("#submit-button");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const answerList = document.querySelector("#answer-list");
const copyButton = document.querySelector("#copy-button");

let currentAnswers = [];

function setLoading(loading) {
  submitButton.disabled = loading;
  input.disabled = loading;
  submitButton.textContent = loading ? "Loading…" : "Get answers";
}

function renderAnswers(answers) {
  answerList.replaceChildren();
  const fragment = document.createDocumentFragment();

  answers.forEach(({ number, task_id: taskId, url, answer }) => {
    const row = document.createElement("div");
    row.className = "answer-row";

    const numberCell = document.createElement("span");
    numberCell.className = "number";
    numberCell.textContent = number;

    const answerCell = document.createElement("span");
    answerCell.className = answer ? "answer" : "answer missing";
    answerCell.textContent = answer || "Answer not found";

    const taskLink = document.createElement("a");
    taskLink.className = "task-link";
    taskLink.href = url;
    taskLink.target = "_blank";
    taskLink.rel = "noopener noreferrer";
    taskLink.textContent = `#${taskId}`;
    taskLink.setAttribute("aria-label", `Open task ${taskId}`);

    row.append(numberCell, answerCell, taskLink);
    fragment.append(row);
  });

  answerList.append(fragment);
  results.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const variant = input.value.trim();
  if (!/^\d{1,12}$/.test(variant)) {
    status.textContent = "Enter a valid test number";
    return;
  }

  setLoading(true);
  status.textContent = "";
  results.hidden = true;
  currentAnswers = [];

  try {
    const response = await fetch(`/api/answers/${encodeURIComponent(variant)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not get answers");
    currentAnswers = data.answers;
    renderAnswers(currentAnswers);
  } catch (error) {
    status.textContent = error.message || "Could not get answers";
  } finally {
    setLoading(false);
  }
});

copyButton.addEventListener("click", async () => {
  const text = currentAnswers
    .map(({ number, answer }) => `${number}\t${answer || "Answer not found"}`)
    .join("\n");
  try {
    await navigator.clipboard.writeText(text);
    copyButton.textContent = "Copied";
    window.setTimeout(() => (copyButton.textContent = "Copy"), 1200);
  } catch {
    status.textContent = "Could not copy answers";
  }
});
