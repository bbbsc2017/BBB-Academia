'use client'
import React from 'react'
import { PenLine, Upload } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { PlanLevel } from '@services/plans/plans'

interface CourseCreationTypeSelectorProps {
  onSelectType: (type: 'scratch' | 'migrate') => void
  currentPlan: PlanLevel
}

function CourseCreationTypeSelector({ onSelectType }: CourseCreationTypeSelectorProps) {
  const { t } = useTranslation()

  return (
    <div className="min-w-[650px] py-2">
      <div className="grid grid-cols-2 gap-4">
        {/* Start from scratch option */}
        <button
          onClick={() => onSelectType('scratch')}
          className="group flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 bg-white hover:border-black hover:shadow-lg transition-all duration-200"
        >
          <div className="w-14 h-14 rounded-full bg-gray-50 flex items-center justify-center mb-4 group-hover:bg-gray-100 transition-colors">
            <PenLine size={28} className="text-gray-600" />
          </div>
          <h3 className="font-semibold text-gray-900 mb-1">
            {t('courses.create.from_scratch')}
          </h3>
          <p className="text-sm text-gray-500 text-center">
            {t('courses.create.from_scratch_description')}
          </p>
        </button>

        {/* Start from existing content option */}
        <button
          onClick={() => onSelectType('migrate')}
          className="group flex flex-col items-center p-6 rounded-xl border-2 border-gray-200 bg-white hover:border-black hover:shadow-lg transition-all duration-200"
        >
          <div className="w-14 h-14 rounded-full bg-emerald-50 flex items-center justify-center mb-4 group-hover:bg-emerald-100 transition-colors">
            <Upload size={28} className="text-emerald-600" />
          </div>
          <h3 className="font-semibold text-gray-900 mb-1">
            {t('courses.create.from_existing')}
          </h3>
          <p className="text-sm text-gray-500 text-center">
            {t('courses.create.from_existing_description')}
          </p>
        </button>
      </div>
    </div>
  )
}

export default CourseCreationTypeSelector
