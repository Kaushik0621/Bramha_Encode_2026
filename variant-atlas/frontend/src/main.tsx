import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ResearchApp from './research/ResearchApp';
import StoryPage from './components/StoryPage';
import './styles.css';
import './theme.css';
const params=new URLSearchParams(location.search);
ReactDOM.createRoot(document.getElementById('root')!).render(params.get('page')==='story'?<StoryPage/>:params.get('workspace')==='fixture'?<React.StrictMode><App/></React.StrictMode>:<ResearchApp/>);
