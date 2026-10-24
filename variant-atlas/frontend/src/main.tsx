import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import ResearchApp from './research/ResearchApp';
import './styles.css';
ReactDOM.createRoot(document.getElementById('root')!).render(new URLSearchParams(location.search).get('workspace')==='fixture'?<React.StrictMode><App/></React.StrictMode>:<ResearchApp/>);
