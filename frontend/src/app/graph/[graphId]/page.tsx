import { GraphView } from "@/features/graph/graph-view";

export default async function Page({ params }: { params: Promise<{ graphId: string }> }) {
  const { graphId } = await params;
  return <GraphView graphId={graphId} />;
}
