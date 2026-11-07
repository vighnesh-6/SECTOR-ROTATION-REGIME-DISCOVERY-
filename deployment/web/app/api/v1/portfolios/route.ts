import { NextRequest, NextResponse } from "next/server";
import { queryNeon } from "@/lib/neon";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const variant = searchParams.get("variant"); // "1A", "1B", "2A", "2B" or null
    const fromDate = searchParams.get("from_date") || "2025-01-01"; // Default to holdout period
    const toDate = searchParams.get("to_date") || "2099-12-31";

    let simSql = `
      SELECT 
        variant,
        date::text as date,
        period,
        rebalance_executed,
        actual_turnover,
        transaction_cost,
        net_return,
        net_nav,
        accepted_regime,
        w_post_auto,
        w_post_bank,
        w_post_fmcg,
        w_post_it,
        w_post_metal,
        w_post_pharma,
        w_post_cash
      FROM portfolio_simulations_daily
      WHERE date >= $1 AND date <= $2
    `;
    const params: any[] = [fromDate, toDate];

    if (variant) {
      simSql += ` AND variant = $3`;
      params.push(variant.toUpperCase());
    }
    simSql += ` ORDER BY date ASC, variant ASC;`;

    // Fetch benchmark simulations over the same date range
    const benchSql = `
      SELECT 
        benchmark_name,
        date::text as date,
        net_return,
        net_nav
      FROM benchmark_simulations_daily
      WHERE date >= $1 AND date <= $2
      ORDER BY date ASC, benchmark_name ASC;
    `;

    // Fetch latest current holdings per variant
    const latestHoldingsSql = `
      SELECT DISTINCT ON (variant)
        variant,
        date::text as date,
        net_nav,
        accepted_regime,
        w_post_auto,
        w_post_bank,
        w_post_fmcg,
        w_post_it,
        w_post_metal,
        w_post_pharma,
        w_post_cash
      FROM portfolio_simulations_daily
      ORDER BY variant, date DESC;
    `;

    // Execute all 3 independent queries in parallel
    const [simRows, benchRows, latestHoldings] = await Promise.all([
      queryNeon(simSql, params),
      queryNeon(benchSql, [fromDate, toDate]),
      queryNeon(latestHoldingsSql),
    ]);

    return NextResponse.json({
      filters: { variant: variant || "ALL", from_date: fromDate, to_date: toDate },
      total_simulation_records: simRows.length,
      latest_holdings: latestHoldings,
      strategy_simulations: simRows,
      benchmark_simulations: benchRows,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to fetch portfolio performance data" },
      { status: 500 }
    );
  }
}
