import { Navigate } from 'react-router-dom'
import { getToken } from '../api.js'
import MediaKit from './MediaKit.jsx'

export default function MediaKitPreview() {
  if (!getToken()) return <Navigate to="/admin/login" replace />

  let data = null
  try {
    data = JSON.parse(localStorage.getItem('media_kit_preview') || 'null')
  } catch {
    data = null
  }

  if (!data) {
    return (
      <div className="public-loading">
        No draft preview is available. Return to the media-kit studio and click Preview draft.
      </div>
    )
  }

  return <MediaKit initialData={data} previewMode />
}
