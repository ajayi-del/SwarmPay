/**
 * SwarmPay Lit Action: 4-Condition Policy Engine
 * 
 * Rules:
 *   1. DOUBLE PAY   — no duplicate payments for the same sub-task
 *   2. COORD AUTH   — only coordinator wallets may sign
 *   3. BUDGET CAP   — coordinator allocation ceiling
 *   4. REP GATE     — reputation score → proportional budget cap (never zero)
 * 
 * Injected automatically via jsParams:
 * - amount: float
 * - sub_task: object
 * - reputation: float
 * - from_wallet: object
 * - to_wallet: object
 * - dataToSign: string (hash to sign)
 * - publicKey: string (PKP uncompressed pub key)
 * - sigName: string (signature identifier)
 */

const evaluatePayment = async () => {
    try {
        // 1. Double Pay Check
        if (sub_task.status === "paid") {
            Lit.Actions.setResponse({response: JSON.stringify({ allow: false, reason: "DOUBLE PAY BLOCK: sub-task already settled" })});
            return;
        }

        // 2. Coordinator Auth Check
        if (from_wallet.role !== "coordinator") {
            Lit.Actions.setResponse({response: JSON.stringify({ allow: false, reason: "AUTH BLOCK: only coordinator wallet may sign payments" })});
            return;
        }

        // 3. Budget Cap Check
        const allocated = parseFloat(sub_task.budget_allocated || amount);
        if (amount > allocated) {
            Lit.Actions.setResponse({response: JSON.stringify({ allow: false, reason: `BUDGET BLOCK: requested ${amount} USDC exceeds coordinator allocation ${allocated} USDC` })});
            return;
        }

        // 4. Reputation Gate Check
        const getRepMultiplier = (rep) => {
            if (rep >= 4.5) return 1.0;
            if (rep >= 3.5) return 0.85;
            if (rep >= 2.5) return 0.65;
            if (rep >= 1.5) return 0.45;
            return 0.20; // Probation floor
        };

        const multiplier = getRepMultiplier(parseFloat(reputation));
        const effectiveCap = allocated * multiplier;
        const isProbation = parseFloat(reputation) < 3.5;

        if (amount > effectiveCap) {
            const reason = `REP GATE: ${sub_task.agent_id || 'AGENT'} capped at ${effectiveCap.toFixed(4)} USDC (${(multiplier * 100).toFixed(0)}% of budget · ${isProbation ? 'probation' : 'rep tier'})`;
            Lit.Actions.setResponse({response: JSON.stringify({ allow: false, reason, is_probation: isProbation, effective_cap: effectiveCap })});
            return;
        }

        // If all checks pass
        Lit.Actions.setResponse({
            response: JSON.stringify({ allow: true })
        });
        
        // Ensure signing is executed
        if (dataToSign && publicKey && sigName) {
            Lit.Actions.signEcdsa({ toSign: dataToSign, publicKey, sigName });
        }
    } catch (e) {
        Lit.Actions.setResponse({response: JSON.stringify({ allow: false, reason: `LIT ACTION ERROR: ${e.message}` })});
    }
};

evaluatePayment();
