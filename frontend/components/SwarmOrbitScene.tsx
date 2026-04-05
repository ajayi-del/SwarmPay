"use client";

/**
 * SwarmOrbitScene — Three.js/R3F mission-control visualization.
 *
 * Business logic wired:
 *  • Agent spheres sized by budget_allocated (bigger spend = bigger body)
 *  • Color matches agent roleColor
 *  • Orbit speed reflects status: working=fast, paid=slow, blocked=stopped+red
 *  • Payment flow lines connect agents that have peer transactions
 *  • Lead agent has a gold halo ring and sits in the inner orbit
 *  • REGIS (coordinator) is at the center, always gold
 *
 * Single WebGL canvas — performant regardless of agent count.
 * Loaded dynamically (ssr: false) to avoid Next.js hydration issues.
 */

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Line, Text } from "@react-three/drei";
import * as THREE from "three";
import type { SubTask, Payment } from "@/lib/api";
import { AGENT_PERSONAS } from "@/lib/personas";

// ── Agent mesh ─────────────────────────────────────────────────────────────────

interface AgentMeshProps {
  position: [number, number, number];
  color: string;
  status: SubTask["status"];
  name: string;
  size: number;
  isLead: boolean;
  orbitRadius: number;
  orbitSpeed: number;
  orbitOffset: number;
}

function AgentMesh({ position, color, status, name, size, isLead, orbitRadius, orbitSpeed, orbitOffset }: AgentMeshProps) {
  const ref = useRef<THREE.Mesh>(null);
  const labelRef = useRef<THREE.Mesh>(null);

  const isWorking  = status === "working";
  const isBlocked  = status === "blocked" || status === "failed";
  const isTerminal = ["complete", "paid"].includes(status);
  const isDead     = status === "timed_out";

  const emissiveColor = isBlocked ? "#ef4444" : isTerminal ? "#22c55e" : color;
  const emissiveIntensity = isWorking ? 0.7 : isTerminal ? 0.4 : isBlocked ? 0.6 : 0.2;
  const meshColor = isDead ? "#333" : color;

  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime;

    // Orbit motion
    const speed = isDead ? 0 : isWorking ? orbitSpeed * 1.8 : isBlocked ? 0 : orbitSpeed;
    ref.current.position.x = Math.cos(t * speed + orbitOffset) * orbitRadius;
    ref.current.position.z = Math.sin(t * speed + orbitOffset) * orbitRadius;
    ref.current.position.y = position[1] + Math.sin(t * 0.5 + orbitOffset) * 0.15;

    // Self-rotation
    ref.current.rotation.y += isWorking ? 0.03 : 0.008;
    ref.current.rotation.x += isWorking ? 0.015 : 0.003;

    // Scale pulse when working
    if (isWorking) {
      const pulse = 1 + Math.sin(t * 3) * 0.07;
      ref.current.scale.setScalar(pulse);
    }

    // Update label to face camera
    if (labelRef.current) {
      labelRef.current.position.x = ref.current.position.x;
      labelRef.current.position.y = ref.current.position.y + size + 0.35;
      labelRef.current.position.z = ref.current.position.z;
    }
  });

  return (
    <>
      <mesh ref={ref} position={position}>
        {/* Agent body — icosahedron for dimensionality */}
        <icosahedronGeometry args={[size, 1]} />
        <meshStandardMaterial
          color={meshColor}
          emissive={emissiveColor}
          emissiveIntensity={emissiveIntensity}
          metalness={0.6}
          roughness={0.25}
          transparent={isDead}
          opacity={isDead ? 0.3 : 1}
        />
      </mesh>

      {/* Lead halo ring */}
      {isLead && (
        <mesh position={position}>
          <torusGeometry args={[size + 0.2, 0.035, 8, 32]} />
          <meshStandardMaterial color="#FFD700" emissive="#FFD700" emissiveIntensity={0.8} />
        </mesh>
      )}

      {/* Agent name label */}
      <Text
        ref={labelRef as React.Ref<THREE.Mesh>}
        fontSize={0.22}
        color={isDead ? "#555" : color}
        anchorX="center"
        anchorY="middle"
        font="/fonts/JetBrainsMono-Regular.woff"
      >
        {name}
      </Text>
    </>
  );
}

// ── REGIS center core ─────────────────────────────────────────────────────────

function RegisCore({ taskStatus }: { taskStatus: string }) {
  const ref = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);

  const isActive = taskStatus === "in_progress";

  useFrame((state) => {
    if (!ref.current || !ringRef.current) return;
    const t = state.clock.elapsedTime;
    ref.current.rotation.y += 0.005;
    ref.current.rotation.x += 0.003;
    ringRef.current.rotation.z = t * 0.3;
    ringRef.current.rotation.x = Math.PI / 2 + Math.sin(t * 0.5) * 0.1;
  });

  return (
    <>
      {/* REGIS dodecahedron */}
      <mesh ref={ref}>
        <dodecahedronGeometry args={[0.7, 0]} />
        <meshStandardMaterial
          color="#FFD700"
          emissive="#FFD700"
          emissiveIntensity={isActive ? 0.6 : 0.3}
          metalness={0.9}
          roughness={0.1}
        />
      </mesh>

      {/* Sovereign ring */}
      <mesh ref={ringRef}>
        <torusGeometry args={[1.1, 0.04, 8, 64]} />
        <meshStandardMaterial color="#FFD700" emissive="#FFD700" emissiveIntensity={0.5} />
      </mesh>

      {/* Label */}
      <Text fontSize={0.26} color="#FFD700" anchorX="center" anchorY="middle" position={[0, 1.2, 0]}
            font="/fonts/JetBrainsMono-Regular.woff">
        REGIS
      </Text>
    </>
  );
}

// ── Payment flow lines ─────────────────────────────────────────────────────────

function PaymentFlowLine({
  fromPos,
  toPos,
  amount,
  status,
}: {
  fromPos: [number, number, number];
  toPos: [number, number, number];
  amount: number;
  status: "signed" | "blocked";
}) {
  const color = status === "signed" ? "#22c55e" : "#ef4444";
  const opacity = status === "signed" ? 0.55 : 0.35;

  return (
    <Line
      points={[fromPos, [0, 0, 0], toPos]}
      color={color}
      lineWidth={Math.max(0.5, amount * 0.5)}
      transparent
      opacity={opacity}
      dashed
      dashScale={2}
    />
  );
}

// ── Main scene ─────────────────────────────────────────────────────────────────

interface SceneProps {
  subTasks: SubTask[];
  payments: Payment[];
  taskStatus: string;
}

function Scene({ subTasks, payments, taskStatus }: SceneProps) {
  const agentCount = subTasks.length;

  const agentData = useMemo(() => {
    const orbitRadius = agentCount <= 2 ? 2.2 : agentCount <= 4 ? 2.8 : 3.5;
    const maxBudget = Math.max(...subTasks.map((s) => s.budget_allocated), 0.001);

    return subTasks.map((st, i) => {
      const persona = AGENT_PERSONAS[st.agent_id];
      const color = persona?.roleColor ?? "#6c63ff";
      const angleOffset = (i / agentCount) * Math.PI * 2;
      const size = 0.28 + (st.budget_allocated / maxBudget) * 0.22; // 0.28–0.50

      return {
        id: st.id,
        name: st.agent_id,
        color,
        status: st.status,
        isLead: !!st.is_lead,
        size,
        orbitRadius,
        orbitSpeed: 0.18,
        orbitOffset: angleOffset,
        walletId: st.wallet_id,
        // Initial position (will be overridden by useFrame)
        position: [
          Math.cos(angleOffset) * orbitRadius,
          0,
          Math.sin(angleOffset) * orbitRadius,
        ] as [number, number, number],
      };
    });
  }, [subTasks, agentCount]);

  // Build payment flow lines from peer payments.
  // Since agents orbit dynamically, we use their base angle positions
  // (t=0 snapshot) which gives approximate but meaningful connection arcs.
  const paymentLines = useMemo(() => {
    const walletToData = new Map(agentData.map((a) => [a.walletId, a]));
    return payments
      .filter((p) => p.policy_reason?.startsWith("PEER:"))
      .map((p) => {
        const from = walletToData.get(p.from_wallet_id);
        const to   = walletToData.get(p.to_wallet_id);
        if (!from || !to) return null;
        return { from, to, amount: p.amount, status: p.status, id: p.id };
      })
      .filter(Boolean) as { from: typeof agentData[0]; to: typeof agentData[0]; amount: number; status: "signed" | "blocked"; id: string }[];
  }, [payments, agentData]);

  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.3} />
      <pointLight position={[3, 5, 3]} intensity={1.2} color="#ffffff" />
      <pointLight position={[-3, -3, -3]} intensity={0.4} color="#6c63ff" />

      {/* REGIS center */}
      <RegisCore taskStatus={taskStatus} />

      {/* Agent bodies */}
      {agentData.map((a) => (
        <AgentMesh key={a.id} {...a} />
      ))}

      {/* Peer payment flow lines */}
      {paymentLines.map((pl) => (
        <PaymentFlowLine
          key={pl.id}
          fromPos={pl.from.position}
          toPos={pl.to.position}
          amount={pl.amount}
          status={pl.status}
        />
      ))}

      {/* Camera control */}
      <OrbitControls
        enablePan={false}
        minDistance={3}
        maxDistance={12}
        autoRotate
        autoRotateSpeed={0.3}
        enableDamping
        dampingFactor={0.08}
      />
    </>
  );
}

// ── Exported component ─────────────────────────────────────────────────────────

interface Props {
  subTasks: SubTask[];
  payments: Payment[];
  taskStatus: string;
}

export default function SwarmOrbitScene({ subTasks, payments, taskStatus }: Props) {
  if (subTasks.length === 0) return null;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        height: 280,
      }}
    >
      {/* Header */}
      <div className="px-4 py-2 flex items-center justify-between" style={{ borderBottom: "1px solid var(--border)" }}>
        <p className="text-label">Swarm Orbit</p>
        <div className="flex items-center gap-3 text-xs font-jb" style={{ color: "var(--text-dim)" }}>
          <span className="flex items-center gap-1">
            <span style={{ color: "#FFD700", fontSize: 8 }}>●</span> REGIS
          </span>
          <span className="flex items-center gap-1">
            <span style={{ color: "#FFD700", fontSize: 8 }}>★</span> Lead
          </span>
          <span className="flex items-center gap-1">
            <span style={{ color: "var(--text-dim)", fontSize: 8 }}>○</span> Drag to explore
          </span>
        </div>
      </div>

      {/* Three.js Canvas */}
      <Canvas
        camera={{ position: [0, 3.5, 7], fov: 55 }}
        style={{ height: 234 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <Scene subTasks={subTasks} payments={payments} taskStatus={taskStatus} />
      </Canvas>
    </div>
  );
}
