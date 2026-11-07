import { NextResponse } from "next/server";
import { queryNeon } from "@/lib/neon";

export const dynamic = "force-dynamic";

const REGIME_ECONOMIC_NAMES: Record<number, string> = {
  0: "Cyclical Reflation Rally",
  1: "High-Volatility Post-Crash Bounce",
  2: "Low-Volatility Consolidation / Base",
  3: "Acute Liquidation / Flight to Safety",
  4: "Steady Expansion / Low-Volatility Bull",
  5: "Correction / Risk-Off Digestion",
};

export async function GET() {
  try {
    // 1. Fetch latest regime inference row
    const rows = await queryNeon(`
      SELECT 
        date::text as date,
        period,
        prob_0,
        prob_1,
        prob_2,
        prob_3,
        prob_4,
        prob_5,
        raw_regime_argmax,
        max_probability,
        is_confident,
        accepted_regime
      FROM regime_inference_daily
      ORDER BY date DESC
      LIMIT 1;
    `);

    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "No regime inference records found." }, { status: 404 });
    }

    const latest = rows[0];
    const acceptedId = parseInt(latest.accepted_regime);

    // 2. Fetch current portfolio target allocations for this date
    const allocRows = await queryNeon(
      `
      SELECT 
        variant,
        holding_days_after,
        rebalance_triggered,
        rebalance_bypassed_r3,
        turnover,
        w_nifty50,
        w_auto,
        w_bank,
        w_fmcg,
        w_it,
        w_metal,
        w_pharma,
        w_cash
      FROM portfolio_allocations_daily
      WHERE date = $1
      ORDER BY variant ASC;
    `,
      [latest.date]
    );

    // 3. Format probabilities array
    const probabilities = [
      { id: 0, name: REGIME_ECONOMIC_NAMES[0], prob: parseFloat(latest.prob_0) },
      { id: 1, name: REGIME_ECONOMIC_NAMES[1], prob: parseFloat(latest.prob_1) },
      { id: 2, name: REGIME_ECONOMIC_NAMES[2], prob: parseFloat(latest.prob_2) },
      { id: 3, name: REGIME_ECONOMIC_NAMES[3], prob: parseFloat(latest.prob_3) },
      { id: 4, name: REGIME_ECONOMIC_NAMES[4], prob: parseFloat(latest.prob_4) },
      { id: 5, name: REGIME_ECONOMIC_NAMES[5], prob: parseFloat(latest.prob_5) },
    ];

    return NextResponse.json({
      date: latest.date,
      period: latest.period,
      accepted_regime: {
        id: acceptedId,
        economic_name: REGIME_ECONOMIC_NAMES[acceptedId] || "Unknown Regime",
        is_confident: latest.is_confident,
        max_probability: parseFloat(latest.max_probability),
        raw_argmax: parseInt(latest.raw_regime_argmax),
      },
      probabilities,
      current_allocations: allocRows,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to fetch latest regime" },
      { status: 500 }
    );
  }
}

