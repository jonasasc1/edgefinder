import { Component, type ErrorInfo, type ReactNode } from "react";

import { Card } from "./Card";
import { Button, EmptyState } from "./EmptyState";
import { isChunkError, reloadOnce } from "../lib/chunkError";

type Props = { children: ReactNode; resetKey?: string; fullPage?: boolean };
type State = { error: Error | null };

/**
 * Fängt Render-Fehler ab, damit nie der ganze Baum verschwindet (schwarzer Schirm).
 * Ladefehler von Seiten-Chunks (alte Version nach einem Deploy) lösen einmal automatisch einen
 * Neuladevorgang aus; danach erscheint die Meldung mit Button. `resetKey` (Pfad) setzt den Fehler
 * beim Seitenwechsel zurück, sodass die Navigation weiter funktioniert.
 */
export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Seitenfehler:", error, info.componentStack);
    if (isChunkError(error)) reloadOnce();
  }

  componentDidUpdate(prev: Props) {
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null });
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const chunk = isChunkError(error);
    return (
      <div className={this.props.fullPage ? "mx-auto max-w-xl p-6 pt-24" : "p-4 lg:p-8"} role="alert">
        <Card>
          <EmptyState
            art="error"
            title="Diese Seite konnte nicht angezeigt werden"
            text={
              chunk
                ? "Es gibt eine neue Version der App. Lade die Seite neu, dann geht es weiter."
                : "Beim Anzeigen ist ein Fehler aufgetreten. Ein Neuladen behebt das meistens. Die Navigation funktioniert weiterhin."
            }
            action={<Button onClick={() => location.reload()}>Erneut laden</Button>}
          />
        </Card>
      </div>
    );
  }
}
