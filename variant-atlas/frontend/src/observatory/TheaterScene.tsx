import AgentNetwork from '../agents/AgentNetwork';
import type {NetworkMessage} from '../agents/AgentNetwork';
import type {Worker,MissionEvent} from './types';
export default function TheaterScene({tasks,messages,selected,onSelect}:{tasks:Worker[];messages?:NetworkMessage[];event?:MissionEvent;selected:string;onSelect:(id:string)=>void;motion:boolean}){return <div className="ob-team-theater"><AgentNetwork nodes={tasks.map(t=>({id:t.id,role:t.role,status:t.status,engine:t.engine,provider:t.provider,model:t.model,parent:t.parent,outputs:t.claims?.length||0,outputLabel:'source observations',summary:t.summary}))} messages={messages} selected={selected} onSelect={onSelect}/></div>;}
