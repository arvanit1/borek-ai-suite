interface AppPageHeaderProps {
  kicker?: string;
  title: string;
  lead: string;
}

export function AppPageHeader({ kicker, title, lead }: AppPageHeaderProps) {
  return (
    <header className="app-page-header">
      {kicker ? <p className="app-page-kicker">{kicker}</p> : null}
      <h1>{title}</h1>
      <p className="app-page-lead">{lead}</p>
    </header>
  );
}
