import { useEffect, useState } from "react";
import { armShort } from "./types";

/** A simulação que está rodando agora: qual é e quanto dela já passou */
export interface RunningSimulation {
  arm: string;
  seed: number;
   /** Quantas seeds cada braço roda, que é o denominador do rótulo */
  seeds: number;
  share: number;
}

/** O andamento da comparação em curso: as simulações fechadas, a fração de passos que o motor já deu e quando esta execução começou */
export interface RunProgress {
   /** O nome da comparação que está rodando, para o card não aparecer sobre outra */
  name: string;
  done: number;
  total: number;
   /** Nulo nas comparações criadas antes de a conta de passos existir */
  share: number | null;
  startedAt: number;
  current: RunningSimulation | null;
}

/** A fração da comparação: os passos, ou as simulações fechadas quando não há teto de passos */
export function shareOf(progress: RunProgress): number {
  if (progress.share != null) return progress.share;
  return progress.total ? progress.done / progress.total : 0;
}

/** A barra é da simulação em curso; os tempos, da comparação inteira */
export function RunProgressCard({ progress }: { progress: RunProgress }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(tick);
  }, []);

  const current = progress.current;
  const share = current ? current.share : shareOf(progress);
  const elapsed = Math.max(0, now - progress.startedAt);
  const whole = shareOf(progress);
  const left = whole > 0 ? elapsed / whole - elapsed : null;

  return (
    <div className="panel run-progress">
      <p className="progress-now">
        {current
          ? `Simulando ${armShort(current.arm)} (${current.seed}/${current.seeds})`
          : "Na fila"}
        <span>{Math.floor(share * 100)}%</span>
      </p>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.floor(share * 100)}
      >
        <div className="progress-fill" style={{ width: `${share * 100}%` }} />
      </div>
      <p className="progress-line">
        <span>
          {progress.done} de {progress.total} simulações
        </span>
        <span>{formatSpan(elapsed)} percorridos</span>
        {left != null && <span>faltam ~{formatSpan(left)}</span>}
      </p>
    </div>
  );
}

/** Um intervalo em segundos, minutos ou horas, com uma casa de precisão só */
export function formatSpan(ms: number): string {
  const seconds = Math.round(ms / 1_000);
  if (seconds < 60) return `${seconds} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
}
