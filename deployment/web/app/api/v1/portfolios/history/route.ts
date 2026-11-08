import { NextRequest, NextResponse } from 'next/server';
import { queryNeon } from '@/lib/neon';
import { dates, integer, apiError } from '@/lib/http';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  try {
    const params = new URL(request.url).searchParams;
    const sessions = integer(params.get('recent_sessions'), 15, 10, 15);
    const { from, to } = dates(params, '2019-11-01', '2099-12-31');
    const [recent, turnover, decisions] = await Promise.all([
      queryNeon(`
        WITH recent_dates AS (
          SELECT DISTINCT date FROM portfolio_simulations_daily
          ORDER BY date DESC LIMIT $1
        )
        SELECT variant, date::text AS date, net_nav
        FROM portfolio_simulations_daily
        WHERE date IN (SELECT date FROM recent_dates)
        ORDER BY date, variant
      `, [sessions]),
      queryNeon(`
        WITH entire_history AS (
          SELECT variant, date, actual_turnover,
            CASE WHEN COUNT(*) OVER running = COUNT(actual_turnover) OVER running
              THEN SUM(actual_turnover) OVER running END AS cumulative_all_history
          FROM portfolio_simulations_daily
          WINDOW running AS (PARTITION BY variant ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
        SELECT variant, date::text AS date, actual_turnover, cumulative_all_history,
          CASE WHEN COUNT(*) OVER selected_window = COUNT(actual_turnover) OVER selected_window
            THEN SUM(actual_turnover) OVER selected_window END AS cumulative_selected_period
        FROM entire_history
        WHERE date >= $1::date AND date <= $2::date
        WINDOW selected_window AS (PARTITION BY variant ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        ORDER BY date, variant
      `, [from, to]),
      queryNeon(`
        SELECT a.variant, a.date::text AS signal_date,
          a.exec_date::text AS scheduled_execution_date,
          a.incumbent_regime_before, a.incumbent_regime_after,
          a.holding_days_before, a.holding_days_after,
          a.rebalance_triggered, a.rebalance_bypassed_r3,
          a.turnover AS decision_turnover,
          r.raw_argmax, r.accepted_regime, r.max_probability, r.is_confident,
          e.date::text AS execution_record_date,
          e.rebalance_executed AS execution_rebalance_executed,
          CASE WHEN e.rebalance_executed THEN e.date::text END AS actual_execution_date,
          e.actual_turnover AS execution_actual_turnover
        FROM portfolio_allocations_daily a
        LEFT JOIN regime_inference_daily r ON r.date = a.date
        LEFT JOIN portfolio_simulations_daily e ON e.variant = a.variant AND e.date = a.exec_date
        WHERE a.date >= $1::date AND a.date <= $2::date
        ORDER BY a.date, a.variant
      `, [from, to]),
    ]);
    return NextResponse.json({
      selected_window: { from_date: from, to_date: to },
      recent_sessions_requested: sessions,
      recent_sessions_returned: new Set(recent.map(row => row.date)).size,
      recent_nav: recent,
      turnover_history: turnover,
      rebalance_history: decisions,
      scopes: {
        recent_nav: 'Latest stored simulation dates, independent of the selected evaluation window. Net NAV is not rebased.',
        cumulative_selected_period: 'Sum of stored daily actual_turnover from the selected start through each row date, inclusive.',
        cumulative_all_history: 'Sum of stored daily actual_turnover from the first stored simulation through each row date, inclusive; excludes later dates.',
        missing_turnover: 'An unavailable turnover input makes that cumulative scope unavailable; no zero is substituted.',
        execution: 'Simulation execution record on the stored scheduled date, not a brokerage fill or an inferred execution.',
      },
    });
  } catch (error) {
    return apiError(error);
  }
}
