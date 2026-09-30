import React,{useEffect,useState}from'react';
import{api}from'./api.js';
import{ShieldCheck,AlertTriangle,RefreshCw}from'lucide-react';

export default function ComplianceStatus({token}){
  const[data,setData]=useState(null),[ruleData,setRuleData]=useState(null),[error,setError]=useState('');
  const load=()=>{setError('');Promise.all([api('/api/tests',{token}),api('/api/rules',{token})]).then(([tests,rules])=>{setData(tests);setRuleData(rules)}).catch(e=>setError(e.message))};
  useEffect(load,[token]);
  if(error)return <div className="failure"><AlertTriangle/><div><b>Unable to load compliance results.</b><span>{error}</span></div><button className="secondary" onClick={load}>Retry</button></div>;
  if(!data||!ruleData)return <div className="loading"><RefreshCw className="spin"/> Loading evaluations…</div>;
  const rows=data.flatMap(t=>t.results.map(r=>({...r,t}))),sets=ruleData.active_rule_sets||[];
  const demo=sets.some(s=>s.non_official);
  return <>
    <div className="page-heading"><div><div className="panel-kicker">RULE EVALUATION</div><h1>Compliance status</h1><p>Measured values, versioned rules and controlled evaluation outcomes.</p></div></div>
    <div className="rule-alert"><ShieldCheck/><div><b>{sets.length?'Active rule configurations':'No active rule configuration'}</b><span>{sets.length?sets.map(s=>`${s.standard_name} ${s.version} · ${s.rule_count} rules · ${s.accuracy_classes.join(', ')}`).join(' | '):'Evaluations remain NOT EVALUATED until an administrator configures applicable rules.'}{demo?' The SIH demo profile is synthetic and non-official; it is not legal guidance.':''}</span></div></div>
    {sets.length>0&&<div className="card table-card compliance-table"><div className="table-wrap"><table><thead><tr><th>CONFIGURATION</th><th>STATUS</th><th>TEST COVERAGE</th><th>CLASSES</th></tr></thead><tbody>{sets.map(s=><tr key={s.id}><td><b>{s.standard_name}</b><small>{s.version}</small></td><td><span className={'coverage-state '+(s.non_official?'missing':'configured')}>{s.status}</span></td><td>{s.test_types.join(', ')}</td><td>{s.accuracy_classes.join(', ')}</td></tr>)}</tbody></table></div></div>}
    {rows.length?<div className="card table-card compliance-table"><div className="table-wrap"><table><thead><tr><th>TEST SESSION</th><th>TEST</th><th>RULE</th><th>CALCULATED VALUE</th><th>PERMITTED LIMIT</th><th>STATUS</th><th>RULE VERSION</th></tr></thead><tbody>{rows.map(r=><tr key={`${r.t.id}-${r.id}`}><td>TS-{String(r.t.id).padStart(4,'0')}<small>{r.t.model} · {r.t.instrument}</small></td><td>{r.test_type}</td><td><b>{r.rule_code||'MISSING_RULE'}</b><small>{r.rule_description}</small></td><td>{r.calculated_value??'Not available'} {r.calculated_unit}</td><td>{r.limit_value??(r.status==='NOT_EVALUATED'?'Not configured':'See comparison details')} {r.limit_unit}</td><td><span className={'coverage-state '+(r.status==='PASS'?'configured':r.status==='FAIL'?'failed':'missing')}>{r.status==='NOT_EVALUATED'?'NOT EVALUATED':r.status}</span></td><td>{r.standard_name} · {r.standard_version}<details><summary>Compared rule limits</summary><p>{r.details}</p></details></td></tr>)}</tbody></table></div></div>:<div className="card"><div className="empty-inline"><div><ShieldCheck/></div><b>No compliance evaluations yet</b><span>Run an evaluation from a test session. Raw values can be inspected before rule configuration is available.</span></div></div>}
  </>;
}
