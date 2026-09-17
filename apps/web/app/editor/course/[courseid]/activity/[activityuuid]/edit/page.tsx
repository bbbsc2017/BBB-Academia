
import { default as React } from 'react'
import { Metadata } from 'next'
import EditorOptionsProvider from '@components/Contexts/Editor/EditorContext'
import EditorLoader from '@components/Objects/Editor/EditorLoader'

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: `Edit Activity`,
    description: 'Edit course activity content',
  }
}

const EditActivity = async (params: any) => {
  const activityuuid = (await params.params).activityuuid
  const courseid = (await params.params).courseid

  return (
    <EditorOptionsProvider options={{ isEditable: true }}>
      <EditorLoader courseid={courseid} activityuuid={activityuuid} />
    </EditorOptionsProvider>
  )
}

export default EditActivity
