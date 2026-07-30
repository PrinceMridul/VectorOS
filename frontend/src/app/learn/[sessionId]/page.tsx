import { Workspace } from "@/features/workspace/workspace";

export default async function Page({ params }: { params: Promise<{ sessionId: string }> }) {
  const { sessionId } = await params;
  return <Workspace sessionId={sessionId} />;
}
