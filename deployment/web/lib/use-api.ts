'use client';
import { useCallback,useEffect,useState } from 'react';
export function useApi<T>(url:string,acceptErrorBody=false){
  const [data,setData]=useState<T|null>(null),[error,setError]=useState<string|null>(null),[loading,setLoading]=useState(true),[version,setVersion]=useState(0);
  const refresh=useCallback(()=>setVersion(v=>v+1),[]);
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setError(null);setData(null);
    fetch(url,{signal:controller.signal,cache:'no-store'}).then(async r=>{
      const body=await r.json();
      if(!r.ok&&!acceptErrorBody)throw new Error(body.error||`Data request failed (HTTP ${r.status}).`);
      return body as T;
    }).then(setData).catch(e=>{if(e.name!=='AbortError')setError('Unable to load data. '+e.message);}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return()=>controller.abort();
  },[url,version,acceptErrorBody]);
  return {data,error,loading,refresh};
}
