import { PlayCircle } from 'lucide-react';

interface VideoPlaceholderProps {
  /** YouTube/Loom embed URL, or a direct video file URL. Omit to show the "coming soon" card. */
  videoUrl?: string;
}

const EMBED_HOSTS = ['youtube.com/embed', 'youtube-nocookie.com/embed', 'loom.com/embed', 'player.vimeo.com'];

export default function VideoPlaceholder({ videoUrl }: VideoPlaceholderProps) {
  if (!videoUrl) {
    return (
      <div
        className="rounded-xl flex flex-col items-center justify-center gap-3 py-20 text-center"
        style={{ background: 'var(--panel)', border: '1px dashed var(--line)' }}
      >
        <PlayCircle className="w-10 h-10" style={{ color: 'var(--mute-dim)' }} />
        <p className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Walkthrough video coming soon
        </p>
        <p className="text-xs max-w-sm" style={{ color: 'var(--mute)' }}>
          A short screen recording of the full loop — issue in, diagnosis, verified fix, approved
          pull request out.
        </p>
      </div>
    );
  }

  const isEmbed = EMBED_HOSTS.some((host) => videoUrl.includes(host));

  return (
    <div
      className="rounded-xl overflow-hidden aspect-video"
      style={{ background: 'var(--panel)', border: '1px solid var(--line)' }}
    >
      {isEmbed ? (
        <iframe
          src={videoUrl}
          title="Sentinel SRE walkthrough"
          className="w-full h-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
        />
      ) : (
        <video src={videoUrl} controls className="w-full h-full" />
      )}
    </div>
  );
}
