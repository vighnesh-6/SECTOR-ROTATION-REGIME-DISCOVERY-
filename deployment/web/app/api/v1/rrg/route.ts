import { NextRequest, NextResponse } from "next/server";
import { queryNeon } from "@/lib/neon";

export const dynamic = "force-dynamic";

const SECTORS = ["AUTO", "BANK", "FMCG", "IT", "METAL", "PHARMA"];

function calculateMeanStd(values: number[]): { mean: number; std: number } {
  const n = values.length;
  if (n < 2) return { mean: values[0] || 0, std: 1.0 };
  const mean = values.reduce((acc, v) => acc + v, 0) / n;
  const variance = values.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / (n - 1);
  return { mean, std: Math.sqrt(variance) || 1e-4 };
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const trailLength = parseInt(searchParams.get("trail") || "5"); // default 5 trailing days

    // Load last 80 sessions of closing prices for NIFTY 50 and the 6 sectors
    const sql = `
      SELECT symbol, date::text as date, close
      FROM index_candles_daily
      WHERE symbol IN ('NIFTY 50', 'NIFTY AUTO', 'NIFTY BANK', 'NIFTY FMCG', 'NIFTY IT', 'NIFTY METAL', 'NIFTY PHARMA')
      ORDER BY date DESC
      LIMIT 80 * 7;
    `;
    const rows = await queryNeon(sql);

    // Group prices by date and symbol
    const pricesByDate: Record<string, Record<string, number>> = {};
    for (const r of rows) {
      if (!pricesByDate[r.date]) pricesByDate[r.date] = {};
      pricesByDate[r.date][r.symbol] = parseFloat(r.close);
    }

    const sortedDates = Object.keys(pricesByDate).sort();
    if (sortedDates.length < 52) {
      return NextResponse.json({ error: "Insufficient historical data for RRG calculation (requires at least 52 sessions)." }, { status: 400 });
    }

    // 1. Compute RS = Sector / NIFTY50
    const rsSeries: Record<string, number[]> = {};
    for (const s of SECTORS) rsSeries[s] = [];

    const validDates: string[] = [];
    for (const d of sortedDates) {
      const dayPrices = pricesByDate[d];
      const pNifty = dayPrices["NIFTY 50"];
      if (!pNifty) continue;
      validDates.push(d);
      for (const s of SECTORS) {
        const pSec = dayPrices[`NIFTY ${s}`];
        rsSeries[s].push(pSec ? pSec / pNifty : 1.0);
      }
    }

    // 2. Compute RS-Ratio (50-day z-score * 10 + 100)
    const rsRatioSeries: Record<string, number[]> = {};
    for (const s of SECTORS) rsRatioSeries[s] = [];

    const lookback = 50;
    const ratioDates: string[] = [];
    for (let i = lookback - 1; i < validDates.length; i++) {
      ratioDates.push(validDates[i]);
      for (const s of SECTORS) {
        const window = rsSeries[s].slice(i - lookback + 1, i + 1);
        const { mean, std } = calculateMeanStd(window);
        const currentRS = rsSeries[s][i];
        const ratio = 100 + 10 * ((currentRS - mean) / std);
        rsRatioSeries[s].push(ratio);
      }
    }

    // 3. Compute RS-Momentum (10-day z-score of RS-Ratio * 10 + 100)
    const momLookback = 10;
    const rrgResults: Record<string, any[]> = {};
    for (const s of SECTORS) rrgResults[s] = [];

    const finalDates: string[] = [];
    for (let j = momLookback - 1; j < ratioDates.length; j++) {
      const dt = ratioDates[j];
      finalDates.push(dt);
      for (const s of SECTORS) {
        const window = rsRatioSeries[s].slice(j - momLookback + 1, j + 1);
        const { mean, std } = calculateMeanStd(window);
        const currentRatio = rsRatioSeries[s][j];
        const momentum = 100 + 10 * ((currentRatio - mean) / std);

        let quadrant = "Leading";
        if (currentRatio >= 100 && momentum >= 100) quadrant = "Leading";
        else if (currentRatio >= 100 && momentum < 100) quadrant = "Weakening";
        else if (currentRatio < 100 && momentum < 100) quadrant = "Lagging";
        else quadrant = "Improving";

        rrgResults[s].push({
          date: dt,
          rs_ratio: parseFloat(currentRatio.toFixed(2)),
          rs_momentum: parseFloat(momentum.toFixed(2)),
          quadrant,
        });
      }
    }

    // Return the latest points with requested trail length
    const output: Record<string, any> = {};
    const latestDate = finalDates[finalDates.length - 1];

    for (const s of SECTORS) {
      const fullTrail = rrgResults[s];
      const slice = fullTrail.slice(-trailLength);
      const current = slice[slice.length - 1];
      output[s] = {
        sector: s,
        current_ratio: current?.rs_ratio ?? 100,
        current_momentum: current?.rs_momentum ?? 100,
        quadrant: current?.quadrant ?? "Leading",
        trail: slice,
      };
    }

    return NextResponse.json({
      benchmark: "NIFTY 50",
      latest_date: latestDate,
      trail_length: trailLength,
      sectors: output,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to calculate Relative Rotation Graph" },
      { status: 500 }
    );
  }
}

