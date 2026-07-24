import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MediaKit from './pages/MediaKit.jsx'
import CollabForm from './pages/CollabForm.jsx'
import AdminLogin from './pages/AdminLogin.jsx'
import AdminDashboard from './pages/AdminDashboard.jsx'
import InvoiceGenerator from './pages/InvoiceGenerator.jsx'
import MediaKitEditor from './pages/MediaKitEditor.jsx'
import AdminLayout from './components/AdminLayout.jsx'
import CollabDetail from './pages/CollabDetail.jsx'
import InvoiceList from './pages/InvoiceList.jsx'
import BrandDirectory from './pages/BrandDirectory.jsx'
import BrandDetail from './pages/BrandDetail.jsx'
import AttentionPage from './pages/AttentionPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MediaKit />} />
        <Route path="/collab" element={<CollabForm />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="collabs/:collabId" element={<CollabDetail />} />
          <Route path="brands" element={<BrandDirectory />} />
          <Route path="brands/:brandId" element={<BrandDetail />} />
          <Route path="attention" element={<AttentionPage />} />
          <Route path="media-kit" element={<MediaKitEditor />} />
          <Route path="invoices" element={<InvoiceList />} />
          <Route path="invoices/new" element={<InvoiceGenerator />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
