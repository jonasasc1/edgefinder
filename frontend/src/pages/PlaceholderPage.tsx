import { useParams } from "react-router";

import { Card } from "../components/Card";
import { EmptyState } from "../components/EmptyState";
import { IconOverview } from "../components/icons";
import { PageHeader } from "../components/PageHeader";

/** Platzhalter für Seiten, die in Etappe f gebaut werden (Navigation funktioniert schon). */
export function PlaceholderPage({ title, text }: { title: string; text: string }) {
  return (
    <>
      <PageHeader title={title} />
      <div className="px-4 sm:px-8">
        <Card>
          <EmptyState icon={<IconOverview size={26} />} title="Diese Seite entsteht noch" text={text} />
        </Card>
      </div>
    </>
  );
}

export function AssetPlaceholder() {
  const { id } = useParams();
  return <PlaceholderPage title={id ?? "Asset"} text="Die Detailseite mit Teilscores, Begründungen und Verlauf folgt in Etappe f." />;
}
