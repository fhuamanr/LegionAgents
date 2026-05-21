"use client";

import { useEffect, useId, useState } from "react";
import mermaid from "mermaid";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function MermaidDiagram({ chart }: Readonly<{ chart: string }>): JSX.Element {
  const id = useId().replace(/:/g, "");
  const [svg, setSvg] = useState<string>("");

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "strict",
      flowchart: {
        curve: "basis",
      },
    });

    let cancelled = false;

    mermaid.render(`diagram-${id}`, chart).then((result) => {
      if (!cancelled) {
        setSvg(result.svg);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [chart, id]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Mermaid Graph</CardTitle>
        <CardDescription>Workflow topology rendered from graph metadata</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-auto rounded-md border bg-background p-4">
          <div className="min-w-[520px]" dangerouslySetInnerHTML={{ __html: svg }} />
        </div>
      </CardContent>
    </Card>
  );
}
