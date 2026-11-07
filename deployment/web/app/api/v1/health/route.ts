import { NextResponse } from "next/server";
import { queryNeon } from "@/lib/neon";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const startTime = Date.now();
    // 1. Test database connection
    const testRows = await queryNeon("SELECT 1 as connected;");
    const isDbConnected = testRows.length > 0 && testRows[0].connected === 1;

    // 2. Fetch latest candle date and counts
    const candleSummary = await queryNeon(`
      SELECT 
        MAX(date)::text as latest_candle_date,
        COUNT(*)::int as total_candles
      FROM index_candles_daily;
    `);

    // 3. Fetch latest regime state
    const regimeSummary = await queryNeon(`
      SELECT 
        date::text as latest_regime_date,
        accepted_regime,
        is_confident,
        max_probability
      FROM regime_inference_daily
      ORDER BY date DESC
      LIMIT 1;
    `);

    // 4. Fetch latest pipeline execution log
    const execLog = await queryNeon(`
      SELECT 
        trigger_type,
        status,
        step_reached,
        records_processed,
        duration_ms,
        created_at::text as executed_at
      FROM pipeline_execution_logs
      ORDER BY created_at DESC
      LIMIT 1;
    `);

    const latencyMs = Date.now() - startTime;

    return NextResponse.json({
      status: "HEALTHY",
      database: {
        connected: isDbConnected,
        latency_ms: latencyMs,
        latest_candle_date: candleSummary[0]?.latest_candle_date || null,
        total_candle_records: candleSummary[0]?.total_candles || 0,
      },
      inference: {
        latest_regime_date: regimeSummary[0]?.latest_regime_date || null,
        accepted_regime: regimeSummary[0]?.accepted_regime ?? null,
        is_confident: regimeSummary[0]?.is_confident ?? null,
        confidence: regimeSummary[0]?.max_probability ? parseFloat(regimeSummary[0].max_probability) : null,
      },
      last_pipeline_execution: execLog[0] || null,
      timestamp: new Date().toISOString(),
    });
  } catch (error: any) {
    return NextResponse.json(
      {
        status: "DEGRADED",
        error: error.message || "Failed health inspection",
        timestamp: new Date().toISOString(),
      },
      { status: 500 }
    );
  }
}

