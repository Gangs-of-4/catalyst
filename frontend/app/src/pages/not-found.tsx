import { Compass } from "lucide-react";

import { AppHeader } from "@/components/app-header";
import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
        <EmptyState
          icon={Compass}
          title="This page doesn't exist"
          description="The link may be old or mistyped."
          action={
            <Button asChild variant="outline">
              <a href="/">Go to the home page</a>
            </Button>
          }
        />
      </main>
    </>
  );
}
