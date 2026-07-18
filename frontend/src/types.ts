export interface ImageInfo {
  id:         string
  filename:   string
  path:       string
  width:      number
  height:     number
  resolution: string
  megapixels: number
  source:     string
}

export interface Monitor {
  name:         string
  width:        number
  height:       number
  x:            number
  y:            number
  is_primary:   boolean
  is_portrait:  boolean
  orientation:  'portrait' | 'landscape'
  scale_factor: number
  manual:       boolean
  resolution:   string
}

export interface Selection {
  images:   string[]
  monitors: string[]
}

export type SortKey = 'name' | 'resolution' | 'aspect' | 'source'
