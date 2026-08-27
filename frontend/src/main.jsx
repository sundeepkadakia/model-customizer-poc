import React, {useEffect, useMemo, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

console.log("VITE_API_URL:", import.meta.env.VITE_API_URL);
console.log("Resolved API:", API);

async function api(path, options={}) {
  const r = await fetch(`${API}${path}`, options);
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const message = body?.detail?.message || body?.detail || body?.message || `Request failed (${r.status})`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return body;
}

function Step({number, title, children, complete=false}) {
  return <section className={complete ? 'complete' : ''}>
    <div className="stephead"><span className="stepnum">{complete ? '✓' : number}</span><h2>{title}</h2></div>
    {children}
  </section>
}

const FEATURES = [
  {number:'01', title:'Bring your best examples', text:'Upload the support replies, sales conversations, or domain answers that already represent your best work.'},
  {number:'02', title:'We handle the training', text:'Your data is normalized, split for validation, and used to create a lightweight model customization on cloud GPUs.'},
  {number:'03', title:'Prove the improvement', text:'Compare the base and customized model on examples it never saw during training before you put it to work.'},
];

function Brand(){
  return <a className="brand" href="#/" aria-label="Model Customizer home">
    <span className="brandMark"><i/><i/><i/></span>
    <span>Model<span>Customizer</span></span>
  </a>;
}

function SiteNav({route}){
  return <nav className="siteNav">
    <Brand/>
    <div className="navLinks">
      <a className={route==='about'?'active':''} href="#/about">About</a>
      <a className={route==='pricing'?'active':''} href="#/pricing">Pricing</a>
      <a href="mailto:hello@modelcustomizer.ai">Contact</a>
    </div>
    <a className="navCta" href="#/customize">Start customizing <span>→</span></a>
  </nav>;
}

function SiteFooter(){
  return <footer className="siteFooter">
    <Brand/>
    <p>Make AI work the way your business does.</p>
    <div><a href="#/about">About</a><a href="#/pricing">Pricing</a><a href="mailto:hello@modelcustomizer.ai">Contact</a></div>
    <small>© {new Date().getFullYear()} Model Customizer</small>
  </footer>;
}

function Home(){
  return <>
    <section className="hero">
      <div className="heroGlow heroGlowOne"/><div className="heroGlow heroGlowTwo"/>
      <div className="heroContent">
        <div className="heroBadge"><span/> AI that learns how you work</div>
        <h1>Your expertise.<br/><em>A better AI.</em></h1>
        <p>Turn your best examples into a customized AI model—without managing training code, GPUs, or machine-learning infrastructure.</p>
        <div className="heroActions">
          <a className="primaryCta" href="#/customize">Customize your model <span>→</span></a>
          <a className="textCta" href="#/about">See how it works <span>↓</span></a>
        </div>
        <div className="trustLine"><span>✓ No ML expertise required</span><span>✓ Keep control of your model</span><span>✓ Validate before deployment</span></div>
      </div>
      <div className="modelVisual" aria-hidden="true">
        <div className="orbit orbitOne"/><div className="orbit orbitTwo"/><div className="orbit orbitThree"/>
        <div className="modelCore"><span>YOUR</span><strong>AI</strong><small>customized</small></div>
        <div className="dataChip chipOne">Your examples <b>↗</b></div>
        <div className="dataChip chipTwo">Measured quality <b>✓</b></div>
        <div className="dataChip chipThree">Ready to use <b>→</b></div>
      </div>
    </section>

    <section className="proofBar"><p>Built for teams that need AI to understand</p><div><span>Customer support</span><span>Specialized knowledge</span><span>Brand voice</span><span>Repeatable workflows</span></div></section>

    <section className="howSection">
      <div className="sectionEyebrow">A clearer path to a better model</div>
      <h2>From examples to evidence<br/>in three simple steps.</h2>
      <div className="featureGrid">{FEATURES.map(feature=><article key={feature.number}>
        <span>{feature.number}</span><div className="featureIcon">{feature.number==='01'?'↥':feature.number==='02'?'✦':'↗'}</div>
        <h3>{feature.title}</h3><p>{feature.text}</p>
      </article>)}</div>
    </section>

    <section className="outcomeSection">
      <div><div className="sectionEyebrow">The important difference</div><h2>Customization you can measure.</h2><p>Training is only useful if the result is actually better. Model Customizer keeps part of your data unseen, then evaluates the customized model against the original.</p><a className="primaryCta dark" href="#/customize">Build your first model <span>→</span></a></div>
      <div className="resultCard"><div className="resultTop"><span>VALIDATION RESULT</span><b>Held-out examples</b></div><div className="resultScore"><span>Reference fit</span><strong>+38<small>%</small></strong></div><div className="resultBars"><i style={{width:'54%'}}/><i className="improved" style={{width:'82%'}}/></div><div className="resultLegend"><span>Base model</span><span>Customized</span></div></div>
    </section>

    <section className="closingCta"><span className="sectionEyebrow">Early access</span><h2>Your best work can teach<br/>your next AI model.</h2><p>Start with the examples you already have. We’ll help with the rest.</p><a className="primaryCta" href="#/customize">Start customizing <span>→</span></a></section>
  </>;
}

function About(){
  return <div className="innerPage">
    <header className="pageHero"><div className="sectionEyebrow">About Model Customizer</div><h1>AI should adapt to your business—not the other way around.</h1><p>We’re building the simplest trustworthy path from real business examples to a model that performs better at a specific job.</p></header>
    <section className="storyGrid"><div><span>Why we exist</span><h2>The gap between a general model and your work is where value gets lost.</h2></div><div><p>General-purpose AI is impressive, but it does not automatically know your standards, your voice, your policies, or what a great answer looks like for your customers.</p><p>Fine-tuning can close that gap, but today it asks teams to understand datasets, model settings, GPU infrastructure, and evaluation. That keeps useful customization out of reach for many businesses.</p><p>Model Customizer turns that technical process into a guided product. You describe the outcome, provide examples, and see evidence of whether the model improved.</p></div></section>
    <section className="principles"><div className="sectionEyebrow">How we build</div><h2>Three principles guide the product.</h2><div className="principleGrid"><article><b>01</b><h3>Plain language first</h3><p>Customers should describe the business outcome, not tune machine-learning jargon.</p></article><article><b>02</b><h3>Evidence over promises</h3><p>Every customization should be tested on examples the model did not train on.</p></article><article><b>03</b><h3>Control stays with you</h3><p>Your data, customization, and deployment choices should remain visible and portable.</p></article></div></section>
    <section className="pageCta"><h2>Help shape the product.</h2><p>We’re inviting early teams to customize real workflows and tell us where the experience needs to improve.</p><a className="primaryCta" href="#/customize">Try the early product <span>→</span></a></section>
  </div>;
}

const PLANS = [
  {name:'Explorer', price:'Free', sub:'For testing your first use case', features:['1 active project','Up to 100 examples','Standard training run','Base vs. customized comparison'], cta:'Start free'},
  {name:'Builder', price:'$99', unit:'/ month', sub:'For individuals and small teams', features:['5 active projects','Up to 1,000 examples','Smart training configuration','Held-out evaluation report','API access'], cta:'Join early access', featured:true},
  {name:'Company', price:'Custom', sub:'For production workflows', features:['Unlimited team members','Larger private datasets','Dedicated model options','Priority training and support','Deployment guidance'], cta:'Talk to us'},
];

function Pricing(){
  return <div className="innerPage pricingPage">
    <header className="pageHero centered"><div className="sectionEyebrow">Simple, transparent plans</div><h1>Start small. Scale when the model proves its value.</h1><p>Early-access pricing is designed to help you validate a real use case before making a larger commitment.</p></header>
    <section className="pricingGrid">{PLANS.map(plan=><article className={plan.featured?'featured':''} key={plan.name}>{plan.featured&&<div className="popular">MOST POPULAR</div>}<h3>{plan.name}</h3><p>{plan.sub}</p><div className="price">{plan.price}<small>{plan.unit}</small></div><a className={plan.featured?'primaryCta':'planCta'} href={plan.name==='Company'?'mailto:hello@modelcustomizer.ai':'#/customize'}>{plan.cta} <span>→</span></a><ul>{plan.features.map(x=><li key={x}>✓ <span>{x}</span></li>)}</ul></article>)}</section>
    <p className="pricingNote">GPU usage limits and final pricing may change during early access. We’ll always show the expected cost before a paid training run.</p>
  </div>;
}

function CustomizerApp(){
  const [project,setProject]=useState(null);
  const [name,setName]=useState('Support Agent');
  const [goal,setGoal]=useState('Respond like our best support representative while staying concise and helpful.');
  const [file,setFile]=useState(null);
  const [mode,setMode]=useState('auto');
  const [promptField,setPromptField]=useState('');
  const [responseField,setResponseField]=useState('');
  const [dataset,setDataset]=useState(null);
  const [status,setStatus]=useState('');
  const [error,setError]=useState('');
  const [job,setJob]=useState(null);
  const [evalJob,setEvalJob]=useState(null);
  const [evaluation,setEvaluation]=useState(null);
  const [prompt,setPrompt]=useState('I was charged twice. Can you help?');
  const [comparison,setComparison]=useState(null);
  const [tunedResponse,setTunedResponse]=useState('');
  const [opJob,setOpJob]=useState(null);
  const [busy,setBusy]=useState(false);

  const [projects, setProjects] = useState([]);

  const trained = project?.adapter_uri || project?.adapter_path || project?.status === 'trained';

  useEffect(() => {
    api('/projects')
      .then(setProjects)
      .catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!job || !['queued','running'].includes(job.status)) return;
    const timer = setInterval(async () => {
      try {
        const x = await api(`/jobs/${job.id}`);
        setJob(x);
        setStatus(`Training ${x.status}`);
        if (x.status === 'completed') {
          const fresh = await api(`/projects/${project.id}`);
          setProject(fresh);
          setStatus('Training completed. Your adapter is ready.');
        }
      } catch (e) { setError(e.message); }
    }, 2000);
    return () => clearInterval(timer);
  }, [job?.id, job?.status, project?.id]);

  useEffect(() => {
    if (!evalJob || !['queued','running'].includes(evalJob.status)) return;
    const timer = setInterval(async () => {
      try {
        const x = await api(`/jobs/${evalJob.id}`);
        setEvalJob(x);
        if (x.status === 'completed') {
          setEvaluation(x.result);
          setStatus('Held-out evaluation completed.');
        } else if (x.status === 'failed') {
          setError(x.log || 'Evaluation failed');
        }
      } catch (e) { setError(e.message); }
    }, 2000);
    return () => clearInterval(timer);
  }, [evalJob?.id, evalJob?.status]);


  useEffect(() => {
    if (!opJob || !['queued','running'].includes(opJob.status)) return;
    const timer = setInterval(async () => {
      try {
        const x = await api(`/jobs/${opJob.id}`);
        setOpJob(x);
        if (x.status === 'completed') {
          if (x.kind === 'comparison') setComparison(x.result);
          if (x.kind === 'generation') setTunedResponse(x.result?.response || '');
          setStatus(x.kind === 'comparison' ? 'Comparison ready.' : 'Tuned response generated.');
        } else if (x.status === 'failed') setError(x.error || 'GPU job failed');
      } catch (e) { setError(e.message); }
    }, 2500);
    return () => clearInterval(timer);
  }, [opJob?.id, opJob?.status]);

  async function run(action){
    setError('');
    setBusy(true);
    try { await action(); } catch(e) { setError(e.message); } finally { setBusy(false); }
  }

  async function loadProject(id) {
    await run(async () => {
      const fresh = await api(`/projects/${id}`);

      setProject(fresh);

      if (fresh.dataset) {
        setDataset({
          ...fresh.dataset,
          examples: fresh.dataset.examples ?? fresh.example_count,
          train_examples: fresh.dataset.train_examples ?? fresh.train_count,
          eval_examples: fresh.dataset.eval_examples ?? fresh.eval_count,
        });
      } else {
        setDataset(null);
      }

      setName(fresh.name || '');
      setGoal(fresh.goal || '');
      setStatus(`Loaded project: ${fresh.name}`);
    });
  }

  async function createProject(){
    await run(async () => {
      const x = await api('/projects',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name,goal,base_model:'Qwen/Qwen3-4B'})
      });
      setProject(x); setStatus('Project created. Add examples next.');
    });
  }

  async function upload(){
    await run(async () => {
      const fd=new FormData();
      fd.append('file',file);
      fd.append('mode',mode);
      if(promptField) fd.append('prompt_field',promptField);
      if(responseField) fd.append('response_field',responseField);
      const x=await api(`/projects/${project.id}/dataset`,{method:'POST',body:fd});
      setDataset(x);
      const fresh=await api(`/projects/${project.id}`); setProject(fresh);
      setStatus(`${x.examples} examples normalized: ${x.train_examples} train + ${x.eval_examples} held out.`);
    });
  }

  async function train(){
    await run(async () => {
      const x=await api(`/projects/${project.id}/train`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({epochs:2,learning_rate:0.0001,lora_rank:8,max_length:256})
      });
      setJob(x); setStatus('Training queued…');
    });
  }

  async function evaluate(){
    await run(async () => {
      const x=await api(`/projects/${project.id}/evaluate`,{method:'POST'});
      setEvalJob(x); setStatus('Evaluating on examples the model did not train on…');
    });
  }

  async function compare(){
    await run(async () => {
      const x=await api(`/projects/${project.id}/compare`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prompt,max_new_tokens:200})
      });
      setOpJob(x); setStatus('Comparison queued on GPU…');
    });
  }

  async function generate(){
    await run(async () => {
      const x=await api(`/projects/${project.id}/generate`,{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({prompt,max_new_tokens:200})
      });
      setOpJob(x); setStatus('Generation queued on GPU…');
    });
  }

  const improvement = evaluation?.reference_fit?.improvement_pct;
  const improvementLabel = useMemo(() => {
    if (improvement == null) return null;
    return `${improvement >= 0 ? '+' : ''}${improvement}%`;
  }, [improvement]);

  return <main className="customizerMain">
    <header className="customizerHeader">
      <div className="eyebrow">MODEL CUSTOMIZER · MVP 0.2</div>
      <h1>Make any AI better for <span>your job.</span></h1>
      <p className="sub">Bring examples in the format you already have. We normalize them, train a small adapter, hold examples back, and show whether the customized model actually fits your desired behavior better.</p>
    </header>

    {error && <div className="alert error"><b>Something needs attention.</b><span>{error}</span></div>}
    {status && <div className="alert"><span>{status}</span></div>}

    <Step number="1" title="Define the outcome" complete={!!project}>
      <label>Project name</label>
      <input value={name} onChange={e=>setName(e.target.value)} disabled={!!project}/>
      <label>What should the AI get better at?</label>
      <textarea value={goal} onChange={e=>setGoal(e.target.value)} disabled={!!project}/>
      <div className="hint">No LoRA jargon here. Describe the business behavior you want.</div>
      {!project && projects.length > 0 && (
        <>
          <label>Resume existing project</label>

          <select
            defaultValue=""
            onChange={e => {
              if (e.target.value) loadProject(e.target.value);
            }}
          >
            <option value="">Select a project...</option>

            {projects.map(p => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.status}
              </option>
            ))}
          </select>

          <div className="hint">
            Continue from a previously created project and its uploaded dataset.
          </div>
        </>
      )}
      {!project && <button disabled={busy} onClick={createProject}>Create project</button>}
      {project && <div className="pill">{project.base_model}</div>}
    </Step>

    <Step number="2" title="Give it examples" complete={!!dataset}>
      {dataset && (
        <div className="alert">
          <span>
            You’re currently using the existing training dataset for this project:
            {' '}
            <strong>{dataset.examples ?? project?.example_count ?? 0}</strong> examples,
            with{' '}
            <strong>{dataset.train_examples ?? project?.train_count ?? 0}</strong> used for training
            and{' '}
            <strong>{dataset.eval_examples ?? project?.eval_count ?? 0}</strong> held out for evaluation.
            You can continue with this dataset, or upload a new file below if you want to replace it with updated examples.
          </span>
        </div>
      )}
      <div className="choiceRow">
        <button className={mode==='auto'?'choice active':'choice'} onClick={()=>setMode('auto')}>Auto-detect</button>
        <button className={mode==='prompt_response'?'choice active':'choice'} onClick={()=>setMode('prompt_response')}>Prompt + ideal response</button>
        <button className={mode==='conversation'?'choice active':'choice'} onClick={()=>setMode('conversation')}>Conversations</button>
      </div>
      <input type="file" accept=".jsonl,.json,.csv" onChange={e=>setFile(e.target.files[0])}/>
      <p className="hint">
        {dataset
          ? 'Upload a new CSV, JSON, or JSONL file only if you want to replace the existing dataset. Common columns such as '
          : 'Accepted: CSV, JSON, JSONL. Common columns such as '} <code>question/answer</code>, <code>customer_message/agent_reply</code>, and <code>prompt/response</code> are detected automatically.</p>
      
      {mode==='prompt_response' && <div className="grid2">
        <div><label>Prompt column <small>(optional)</small></label><input placeholder="e.g. customer_message" value={promptField} onChange={e=>setPromptField(e.target.value)}/></div>
        <div><label>Response column <small>(optional)</small></label><input placeholder="e.g. agent_reply" value={responseField} onChange={e=>setResponseField(e.target.value)}/></div>
      </div>}
      <button disabled={!project||!file||busy} onClick={upload}>{dataset ? 'Replace dataset' : 'Normalize dataset'}</button>
      {dataset && <div className="datasetCard">
        <div><strong>{dataset.examples}</strong><span>Total</span></div>
        <div><strong>{dataset.train_examples}</strong><span>Train</span></div>
        <div><strong>{dataset.eval_examples}</strong><span>Held out</span></div>
        {dataset?.detected?.mode && (
          <div>
            <strong>{dataset.detected.mode}</strong>
            <span>Detected format</span>
          </div>
        )}
      </div>}
    </Step>

    <Step number="3" title="Train the customization" complete={trained}>
      <p className="sectioncopy">
        Training runs on a cloud GPU using a lightweight LoRA adapter. We keep the first run small so you can validate the customization before scaling up.
      </p>
      <button disabled={!dataset||busy||['queued','running'].includes(job?.status)} onClick={train}>{['queued','running'].includes(job?.status)?(job.status==='queued'?'Queued…':'Training…'): trained?'Retrain customization':'Train customization'}</button>
      {job && <div className={`job ${job.status}`}><span>{job.status}</span>{job.status==='failed' && <pre>{job.log}</pre>}</div>}
    </Step>

    <Step number="4" title="Prove it on unseen examples" complete={!!evaluation}>
      <p className="sectioncopy">We intentionally kept part of your upload out of training. This evaluates whether the adapter fits those ideal responses better instead of merely memorizing its training rows.</p>
      <button disabled={!trained||busy||evalJob?.status==='running'} onClick={evaluate}>{evalJob?.status==='running'?'Evaluating…':'Run held-out evaluation'}</button>
      {evaluation && <>
        <div className="metricHero">
          <div><span>Reference-fit improvement</span><strong>{improvementLabel}</strong></div>
          <p>Lower held-out loss is better. This measures how much more probability the tuned model gives your desired responses.</p>
        </div>
        <div className="metrics">
          <div><span>Base loss</span><strong>{evaluation.reference_fit.base_loss}</strong></div>
          <div><span>Tuned loss</span><strong>{evaluation.reference_fit.tuned_loss}</strong></div>
          <div><span>Base perplexity</span><strong>{evaluation.reference_fit.base_perplexity}</strong></div>
          <div><span>Tuned perplexity</span><strong>{evaluation.reference_fit.tuned_perplexity}</strong></div>
        </div>
        <p className="hint">{evaluation.note}</p>
      </>}
    </Step>

    <Step number="5" title="Try the customized model">
      <label>New prompt</label>
      <textarea value={prompt} onChange={e=>setPrompt(e.target.value)}/>
      <div className="buttonRow">
        <button disabled={!trained||busy} onClick={compare}>Compare base vs tuned</button>
        <button className="secondary" disabled={!trained||busy} onClick={generate}>Use tuned model</button>
      </div>
      {comparison&&<div className="comparison">
        <article><div className="articleLabel">BASE MODEL</div><pre>{comparison.base}</pre></article>
        <article className="tuned"><div className="articleLabel">CUSTOMIZED</div><pre>{comparison.tuned}</pre></article>
      </div>}
      {tunedResponse && <article className="singleResponse"><div className="articleLabel">TUNED ENDPOINT RESPONSE</div><pre>{tunedResponse}</pre></article>}
    </Step>

    <footer className="productFooter">Flexible outside. Strict inside. Measurable before deployment.</footer>
  </main>
}

function App(){
  const getRoute=()=>window.location.hash.replace(/^#\/?/,'') || 'home';
  const [route,setRoute]=useState(getRoute);
  useEffect(()=>{const onHash=()=>{setRoute(getRoute());window.scrollTo(0,0)};window.addEventListener('hashchange',onHash);return()=>window.removeEventListener('hashchange',onHash)},[]);
  return <div className="siteShell">
    <SiteNav route={route}/>
    {route==='about'?<About/>:route==='pricing'?<Pricing/>:route==='customize'?<CustomizerApp/>:<Home/>}
    <SiteFooter/>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
