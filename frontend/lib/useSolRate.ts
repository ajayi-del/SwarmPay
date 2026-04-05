"use client";

/**
 * useSolRate — fetches the live SOL/USDC rate from the Meteora/CoinGecko service.
 *
 * Returns:
 *   rate      — 1 SOL = rate USDC (e.g. 79.87)
 *   toSol     — converts USDC → SOL string "◎0.125"
 *   toSolFull — converts USDC → "◎0.125 [10.00 USDC]"
 *   fromSol   — converts SOL input → USDC number for API calls
 *   loaded    — true once rate is fetched
 */

import { useState, useEffect, useCallback } from "react";
import { getMeteoraRate } from "./api";

const SOL_SYMBOL = "◎";
const FALLBACK_RATE = 79.87; // Devnet reference rate — real rate fetched async

let _cachedRate: number | null = null;

export interface SolRateUtils {
  rate: number;
  loaded: boolean;
  toSol: (usdc: number, decimals?: number) => string;
  toSolFull: (usdc: number) => string;
  fromSol: (sol: number) => number;
}

export function useSolRate(): SolRateUtils {
  const [rate, setRate] = useState<number>(_cachedRate ?? FALLBACK_RATE);
  const [loaded, setLoaded] = useState(!!_cachedRate);

  useEffect(() => {
    if (_cachedRate) return; // already fetched
    getMeteoraRate()
      .then((d) => {
        if (d.available && d.rate && d.rate > 0) {
          _cachedRate = d.rate;
          setRate(d.rate);
        }
        setLoaded(true);
      })
      .catch(() => {
        setLoaded(true); // use fallback
      });
  }, []);

  const toSol = useCallback(
    (usdc: number, decimals = 4): string => {
      const sol = usdc / rate;
      return `${SOL_SYMBOL}${sol.toFixed(decimals)}`;
    },
    [rate]
  );

  const toSolFull = useCallback(
    (usdc: number): string => {
      const sol = usdc / rate;
      return `${SOL_SYMBOL}${sol.toFixed(4)} [${usdc.toFixed(2)} USDC]`;
    },
    [rate]
  );

  const fromSol = useCallback(
    (sol: number): number => {
      return parseFloat((sol * rate).toFixed(6));
    },
    [rate]
  );

  return { rate, loaded, toSol, toSolFull, fromSol };
}
