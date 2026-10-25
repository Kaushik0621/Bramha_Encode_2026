import {createContext,useContext,useEffect,useState} from 'react';
import type {ReactNode} from 'react';

export type ThemePreference='light'|'dark'|'system';
const key='bramha-atlas-theme';
const stored=():ThemePreference=>{try{const v=localStorage.getItem(key);return v==='light'||v==='dark'?v:'system';}catch{return 'system';}};
const resolve=(p:ThemePreference)=>p==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):p;
const ThemeContext=createContext({preference:'system' as ThemePreference,theme:'dark' as 'light'|'dark',setPreference:(_p:ThemePreference)=>{}});

export function ThemeProvider({children}:{children:ReactNode}){
 const [preference,setPreference]=useState<ThemePreference>(stored);
 const [systemDark,setSystemDark]=useState(()=>matchMedia('(prefers-color-scheme: dark)').matches);
 const theme=preference==='system'?(systemDark?'dark':'light'):preference;
 useEffect(()=>{const media=matchMedia('(prefers-color-scheme: dark)');const change=()=>setSystemDark(media.matches);media.addEventListener('change',change);const sync=(e:StorageEvent)=>{if(e.key===key||e.key===null)setPreference(stored());};window.addEventListener('storage',sync);return()=>{media.removeEventListener('change',change);window.removeEventListener('storage',sync);};},[]);
 useEffect(()=>{document.documentElement.dataset.theme=theme;document.documentElement.style.colorScheme=theme;document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#0b1923':'#f6f3eb');},[theme]);
 const select=(p:ThemePreference)=>{setPreference(p);try{localStorage.setItem(key,p);}catch{/* Current-tab selection still works when storage is unavailable. */}document.documentElement.dataset.theme=resolve(p);};
 return <ThemeContext.Provider value={{preference,theme,setPreference:select}}>{children}</ThemeContext.Provider>;
}
export const useTheme=()=>useContext(ThemeContext);

export function ThemeToggle(){const {theme,setPreference}=useTheme();return <button type="button" className="atlas-theme-toggle" aria-label={'Switch to '+(theme==='dark'?'light':'dark')+' mode'} title={'Switch to '+(theme==='dark'?'light':'dark')+' mode'} onClick={()=>setPreference(theme==='dark'?'light':'dark')}><svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">{theme==='dark'?<><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>:<path d="M20 15.4A8.5 8.5 0 0 1 8.6 4a8.5 8.5 0 1 0 11.4 11.4Z"/>}</svg><span>{theme==='dark'?'Light':'Dark'}</span></button>;}

export function AppearanceSettings(){const {preference,setPreference}=useTheme();return <section className="pw-card atlas-appearance"><h2>Appearance</h2><p>Choose a color theme for this browser. System follows your device setting.</p><div role="group" aria-label="Color theme">{(['light','dark','system'] as const).map(p=><button key={p} type="button" aria-pressed={preference===p} onClick={()=>setPreference(p)}>{p[0].toUpperCase()+p.slice(1)}</button>)}</div><small>Molecular measurement colors retain the same meaning in both themes.</small></section>;}
