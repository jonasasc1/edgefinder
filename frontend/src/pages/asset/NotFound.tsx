import { useNavigate } from "react-router";

import { Card } from "../../components/Card";
import { Button, EmptyState } from "../../components/EmptyState";
import { IconSearch } from "../../components/icons";
import { PageHeader } from "../../components/PageHeader";

export function NotFound() {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="Nicht gefunden" />
      <div className="px-4 sm:px-8">
        <Card>
          <EmptyState
            icon={<IconSearch size={26} />}
            title="Diese Adresse gibt es nicht"
            text="Wähle eine Seite in der Navigation oder suche ein Asset."
            action={<Button onClick={() => navigate("/")}>Zur Übersicht</Button>}
          />
        </Card>
      </div>
    </>
  );
}
