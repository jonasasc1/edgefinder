import { Card } from "../../components/Card";
import { Skeleton } from "../../components/Skeleton";

export function CardSkeletons({ count = 10 }: { count?: number }) {
  return (
    <div className="asset-grid" aria-busy="true" aria-label="Assets werden geladen">
      {Array.from({ length: count }, (_, index) => (
        <Card key={index} className="flex flex-col p-4 sm:p-5">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="mt-2 h-4 w-28" />
          <div className="my-3 flex flex-col items-center gap-2.5">
            <Skeleton className="size-24 !rounded-chip" />
            <Skeleton className="h-5 w-16 !rounded-chip" />
          </div>
          <Skeleton className="mt-2 h-9 w-full" />
        </Card>
      ))}
    </div>
  );
}

export function RowSkeletons({ count = 10 }: { count?: number }) {
  return (
    <Card variant="group" className="divide-y divide-line" >
      <div aria-busy="true" aria-label="Assets werden geladen" className="divide-y divide-line">
        {Array.from({ length: count }, (_, index) => (
          <div key={index} className="flex min-h-row items-center gap-3 px-4 py-2.5">
            <Skeleton className="size-12 !rounded-chip" />
            <div className="flex-1">
              <Skeleton className="h-5 w-24" />
              <Skeleton className="mt-1.5 h-4 w-40 max-w-full" />
            </div>
            <Skeleton className="h-5 w-20 !rounded-chip" />
          </div>
        ))}
      </div>
    </Card>
  );
}
