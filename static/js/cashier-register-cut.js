const registerCutAudit = document.querySelector("[data-register-cut-audit]");

if (registerCutAudit) {
  const unpaidCount = document.querySelector("[data-unpaid-count]");
  const pendingCount = document.querySelector("[data-pending-count]");
  let requestRunning = false;

  const refreshAuditCounts = async () => {
    if (requestRunning || document.hidden) return;
    requestRunning = true;
    try {
      const url = new URL(registerCutAudit.dataset.auditUrl, window.location.origin);
      url.searchParams.set("date", registerCutAudit.dataset.auditDate);
      const response = await fetch(url, {headers: {Accept: "application/json"}, cache: "no-store"});
      const data = await response.json();
      if (!response.ok) return;
      if (unpaidCount) unpaidCount.textContent = data.unpaid_count;
      if (pendingCount) pendingCount.textContent = data.pending_count;
    } catch (error) {
      // La siguiente consulta vuelve a intentarlo sin interrumpir el corte.
    } finally {
      requestRunning = false;
    }
  };

  window.setInterval(refreshAuditCounts, 5000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshAuditCounts();
  });
}
