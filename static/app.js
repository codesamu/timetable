async function persistCell(input) {
  const payload = {
    date: input.dataset.date,
    worker_index: Number.parseInt(input.dataset.workerIndex, 10),
    value: input.value,
  };

  try {
    const response = await fetch("/api/cell", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Save failed with ${response.status}`);
    }

  } catch (error) {
    console.error("Could not save timetable cell", error);
  }
}



function applyWorkerColors() {
  document.querySelectorAll(".worker-color-dot").forEach((node) => {
    node.style.backgroundColor = node.dataset.color || "#334155";
  });

  document.querySelectorAll(".worker-color-name").forEach((node) => {
    node.style.color = node.dataset.color || "#334155";
  });
}



function setActiveTab(tabId) {
  const tabButton = document.querySelector(
    `[data-tab-button="${tabId}"]`
  );

  const resolvedTabId = tabButton
    ? tabId
    : "timetable";

  document.querySelectorAll("[data-tab-button]").forEach((button) => {

    const active =
      button.dataset.tabButton === resolvedTabId;

    button.classList.toggle(
      "bg-slate-900",
      active
    );

    button.classList.toggle(
      "text-white",
      active
    );

    button.classList.toggle(
      "text-slate-700",
      !active
    );

    button.classList.toggle(
      "hover:bg-slate-100",
      !active
    );

  });


  document.querySelectorAll("[data-tab-panel]").forEach((panel) => {

    const active =
      panel.dataset.tabPanel === resolvedTabId;

    panel.classList.toggle(
      "hidden",
      !active
    );

  });

  localStorage.setItem(
    "active-tab",
    resolvedTabId
  );
}



/* -------------------------
   SHIFT SHORTCUTS
------------------------- */

const shortcuts = {
  d1: "8:00-19:30",
  d2: "7:00-15:00",
  d3: "6:00-14:00",
  n1: "19:30-8:00",
  off: "OFF"
};


/* expand shortcuts when leaving field */
document.addEventListener(
  "blur",
  function (event) {

    if (
      !event.target.matches(
        'input[data-date][data-worker-index]'
      )
    ) return;

    let typed =
      event.target.value
        .trim()
        .toLowerCase();

    if (shortcuts[typed]) {

      event.target.value =
        shortcuts[typed];

      // autosave expanded value
      persistCell(event.target);
    }

  },
  true
);



/* Optional:
   expand shortcut instantly when
   Enter or Space is pressed
*/
document.addEventListener(
  "keydown",
  function (event) {

    if (
      !event.target.matches(
        'input[data-date][data-worker-index]'
      )
    ) return;

    if (
      event.key !== "Enter" &&
      event.key !== " "
    ) return;

    let typed =
      event.target.value
        .trim()
        .toLowerCase();

    if (shortcuts[typed]) {

      event.preventDefault();

      event.target.value =
        shortcuts[typed];

      persistCell(event.target);
    }

  }
);



/* -------------------------
   INIT
------------------------- */

const initialTab =
  localStorage.getItem("active-tab")
  || "timetable";

applyWorkerColors();
setActiveTab(initialTab);



/* tabs */
document.addEventListener(
  "click",
  (event) => {

    const button =
      event.target.closest(
        "[data-tab-button]"
      );

    if (!button) return;

    setActiveTab(
      button.dataset.tabButton
    );

  }
);



/* autosave normal typing */
document.addEventListener(
  "input",
  (event) => {

    if (
      event.target.matches(
        "input[data-date][data-worker-index]"
      )
    ) {
      persistCell(event.target);
    }

  }
);
