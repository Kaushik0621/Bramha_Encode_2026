import ReactDOM from 'react-dom/client';
import WorkspaceApp from './workspace/WorkspaceApp';
import './styles.css';
import {ThemeProvider} from './components/Theme';
import './theme.css';
ReactDOM.createRoot(document.getElementById('root')!).render(<ThemeProvider><WorkspaceApp/></ThemeProvider>);
