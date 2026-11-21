// Läuft vor dem ersten Rendern: setzt den Modus (System oder Wahl aus localStorage),
// damit es kein Aufblitzen im falschen Modus gibt. Gegenstück: src/lib/theme.tsx.
(function () {
  var pref = "system";
  try {
    pref = localStorage.getItem("ef-theme") || "system";
  } catch (e) {}
  var dark = pref === "dark" || (pref !== "light" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  // „Effekte reduzieren“ (persönliche Einstellung, Konto: fx = calm); Gegenstück: src/lib/calm.ts
  try {
    if (localStorage.getItem("ef-fx") === "calm") document.documentElement.dataset.calm = "1";
  } catch (e) {}
})();
