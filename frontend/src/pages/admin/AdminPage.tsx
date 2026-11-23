import { useNavigate } from "react-router";

import { Button, EmptyState } from "../../components/EmptyState";
import { IconAdmin } from "../../components/icons";
import { PageHeader } from "../../components/PageHeader";
import { Skeleton } from "../../components/Skeleton";
import { loadAccount, useAccount } from "../../lib/account";
import { adminVisible } from "../../lib/adminLogic";
import { Card } from "../../components/Card";
import { ClaudeSection } from "./ClaudeSection";
import { JobsSection } from "./JobsSection";
import { ReportSection } from "./ReportSection";
import { SystemSection } from "./SystemSection";
import { UsersSection } from "./UsersSection";
import { useOverview } from "./useAdminData";

function NoAccess() {
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="Admin" />
      <div className="px-4 sm:px-8">
        <Card>
          <EmptyState
            icon={<IconAdmin size={28} />}
            title="Kein Zugriff"
            text="Dieser Bereich ist nur für Administratoren. Alles andere in E-Giant steht dir wie gewohnt zur Verfügung."
            action={<Button onClick={() => navigate("/")}>Zur Übersicht</Button>}
          />
        </Card>
      </div>
    </>
  );
}

function Loading() {
  return (
    <>
      <PageHeader title="Admin" />
      <div role="status" aria-label="Admin-Bereich wird geladen" className="flex flex-col gap-4 px-4 sm:px-8">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    </>
  );
}

function AdminContent() {
  const { state, reload } = useOverview(true);
  if (state.status === "denied") return <NoAccess />;
  if (state.status === "loading") return <Loading />;
  if (state.status === "error") {
    return (
      <>
        <PageHeader title="Admin" />
        <div className="px-4 sm:px-8">
          <Card>
            <EmptyState icon={<IconAdmin size={28} />} title="Admin-Daten nicht erreichbar" text={state.message} action={<Button onClick={() => void reload()}>Erneut laden</Button>} />
          </Card>
        </div>
      </>
    );
  }
  const { data, loadedAt } = state;
  // Neuer Bericht, sobald ein Auftrag fertig wurde (Schlüssel = höchste Nummer eines beendeten Auftrags)
  const reportKey = Math.max(0, ...data.recent_jobs.filter((j) => j.status === "ok" || j.status === "error").map((j) => j.id));
  return (
    <>
      <PageHeader title="Admin" subtitle="Prüfläufe auslösen, Bericht an Claude übergeben, Systemzustand ansehen." />
      <div className="flex flex-col gap-8 px-4 pb-8 sm:px-8">
        <JobsSection overview={data} loadedAt={loadedAt} reload={reload} />
        <ReportSection refreshKey={reportKey} />
        <ClaudeSection overview={data} reload={reload} />
        <SystemSection overview={data} />
        <UsersSection />
      </div>
    </>
  );
}

/** Admin-Bereich. Das Frontend blendet nur ein/aus; der Server prüft jeden Aufruf (403 → „Kein Zugriff“). */
export function AdminPage() {
  const account = useAccount();
  if (account.status === "loading") return <Loading />;
  if (account.status === "error") {
    return (
      <>
        <PageHeader title="Admin" />
        <div className="px-4 sm:px-8">
          <Card>
            <EmptyState icon={<IconAdmin size={28} />} title="Konto nicht erreichbar" text="Ohne Konto lässt sich der Admin-Bereich nicht öffnen." action={<Button onClick={() => void loadAccount()}>Erneut versuchen</Button>} />
          </Card>
        </div>
      </>
    );
  }
  if (!adminVisible(account.status, account.info?.isAdmin)) return <NoAccess />;
  return <AdminContent />;
}
