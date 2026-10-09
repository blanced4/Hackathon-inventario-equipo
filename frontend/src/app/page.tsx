export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-4xl font-bold tracking-tight">
        Inventario Inteligente del Taller
      </h1>
      <p className="max-w-prose text-center text-muted-foreground">
        Sistema de gestión de inventario para husillos y motores industriales.
        Consumiendo eventos en tiempo real desde Redpanda.
      </p>
      <div className="flex gap-4">
        <a
          href="/dashboard"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
        >
          Ir al Dashboard
        </a>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-md border px-4 py-2 text-sm font-medium shadow hover:bg-accent"
        >
          API Docs
        </a>
      </div>
    </main>
  );
}
