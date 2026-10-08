import { Monitor, UsersRound, ChartNoAxesColumnIncreasing, BrainCircuit, GraduationCap, Leaf, Settings2 } from 'lucide-react';
const icons = { informatique: Monitor, conseil: UsersRound, digitalisation: ChartNoAxesColumnIncreasing, 'intelligence-artificielle': BrainCircuit, formation: GraduationCap, formations: GraduationCap, energie: Leaf, settings: Settings2 };
export function ExpertiseIcon({ name, size = 29, className = '' }: { name: string; size?: number; className?: string }) {
  const Icon = icons[name as keyof typeof icons] || Monitor;
  return <Icon size={size} strokeWidth={1.65} className={className} aria-hidden="true" />;
}
