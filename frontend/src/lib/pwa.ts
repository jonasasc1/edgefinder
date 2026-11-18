// PWA: Service Worker anmelden (nur im Produktionsbuild) und Vorbereitung für Push.

export function registerServiceWorker() {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Ohne Service Worker läuft die App normal weiter, nur ohne Offline-Hinweis.
    });
  });
}

/**
 * Push ist nur vorbereitet: der Service Worker kann Meldungen anzeigen, die App abonniert aber
 * nichts und der Server sendet nichts. Ein späteres Abo liefe über `registration.pushManager.subscribe`
 * mit einem VAPID-Schlüssel (Backend: notify/).
 */
export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}
