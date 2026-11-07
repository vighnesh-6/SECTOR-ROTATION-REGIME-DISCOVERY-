import { NextRequest, NextResponse } from "next/server";
import { queryNeon } from "@/lib/neon";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = parseInt(searchParams.get("limit") || "100");
    const category = searchParams.get("category");

    let sql = `
      SELECT 
        event_id,
        date::text as date,
        category,
        title,
        actual as severity,
        forecast as region,
        previous,
        source
      FROM macro_events
    `;
    const params: any[] = [];
    if (category) {
      sql += ` WHERE category ILIKE $1`;
      params.push(`%${category}%`);
    }
    sql += ` ORDER BY date DESC LIMIT ${limit};`;

    const rows = await queryNeon(sql, params);
    return NextResponse.json({ count: rows.length, events: rows });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || "Failed to fetch macro events" },
      { status: 500 }
    );
  }
}

