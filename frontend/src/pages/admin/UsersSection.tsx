import { Badge } from "../../components/Badge";
import { Card } from "../../components/Card";
import { ErrorState } from "../../components/ErrorState";
import { SectionTitle } from "../../components/SectionTitle";
import { Skeleton } from "../../components/Skeleton";
import { Table, Td, Th } from "../../components/Table";
import { fetchAdminUsers } from "../../lib/api";
import { formatAgo, formatDateMedium } from "../../lib/format";
import { useApi } from "../../lib/useApi";

export function UsersSection() {
  const { state, reload } = useApi((signal) => fetchAdminUsers(signal), []);
  return (
    <section aria-labelledby="konten-title">
      <SectionTitle title="Konten" id="konten-title" />
      {state.status === "loading" && <Skeleton className="h-32 w-full" />}
      {state.status === "error" && <ErrorState what="Die Konten" onRetry={reload} />}
      {state.status === "ready" && (
        <Card className="p-4 sm:p-5">
          <Table caption="Konten (nur Ansicht)">
            <thead>
              <tr>
                <Th>E-Mail</Th>
                <Th>Seit</Th>
                <Th>Zuletzt aktiv</Th>
                <Th right>Favoriten</Th>
                <Th>Rolle</Th>
              </tr>
            </thead>
            <tbody>
              {state.data.users.map((user) => (
                <tr key={user.email}>
                  <Td strong>{user.email}</Td>
                  <Td>{formatDateMedium(user.created_at)}</Td>
                  <Td>{formatAgo(user.last_seen_at)}</Td>
                  <Td right>{user.favorites}</Td>
                  <Td>{user.is_admin ? <Badge tone="flat">Admin</Badge> : "Konto"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div className="mt-4 rounded-control bg-fill p-3 text-footnote text-ink-2">
            <p className="font-medium text-ink">Admin vergeben oder entziehen</p>
            <p className="mt-1">Das geht nur direkt auf dem Server („trading“), nie über diese Seite. Beispiel (zum Abtippen, hier nicht ausführbar):</p>
            <pre tabIndex={0} aria-label="Beispielbefehl" className="mt-2 overflow-x-auto whitespace-pre rounded-control bg-surface p-2 text-caption text-ink">
              {"cd /opt/edgefinder\nsudo -u edgefinder .venv/bin/edgefinder admin grant name@example.com"}
            </pre>
            <p className="mt-2">
              Entziehen mit <code>admin revoke</code>, Übersicht mit <code>admin list</code>.
            </p>
          </div>
        </Card>
      )}
    </section>
  );
}
